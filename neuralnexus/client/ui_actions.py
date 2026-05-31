"""
ui_actions.py
-------------
Menu action handlers for the NeuralNexus CLI client.

This module contains all user-facing actions invoked via the menu system,
connecting the UI to the underlying gRPC transport layer (rpc_client.py).
"""

import hashlib
import json
import os

import rpc_client
from rpc_client import answer_query, chat_with_tutor
from session_manager import grpc_helper
from menu_renderer import handle_menu


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Return the SHA-256 hex digest of a plaintext password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _print_error(message) -> None:
    print(f"ERROR: {message}")


# ---------------------------------------------------------------------------
# Main menu actions
# ---------------------------------------------------------------------------

def student_login():
    """Prompt for student credentials and navigate to the student sub-menu."""
    username = input("Username: ")
    password = input("Password: ")
    token, error = rpc_client.student_login(username, _hash_password(password))
    if error:
        _print_error(error)
        return None, False
    grpc_helper.set_access_token(token)
    return {
        "options": STUDENT_MENU_OPTIONS,
        "actions": STUDENT_MENU_ACTIONS,
        "head": "Student Menu",
    }, False


def faculty_login():
    """Prompt for faculty credentials and navigate to the faculty sub-menu."""
    username = input("Username: ")
    password = input("Password: ")
    token, error = rpc_client.faculty_login(username, _hash_password(password))
    if error:
        _print_error(error)
        return None, False
    grpc_helper.set_access_token(token)
    return {
        "options": FACULTY_MENU_OPTIONS,
        "actions": FACULTY_MENU_ACTIONS,
        "head": "Faculty Menu",
    }, False


def logout():
    """Clear the active session token."""
    grpc_helper.set_access_token(None)
    print("Logged out.")
    return None, False


MAIN_MENU_OPTIONS = (
    (1, "Student Login"),
    (2, "Faculty Login"),
    (3, "Logout"),
)

MAIN_MENU_ACTIONS = {
    1: student_login,
    2: faculty_login,
    3: logout,
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fetch_and_display_course_contents():
    """
    Fetch course material list, display it, and offer a download prompt.

    Returns (None, False) after user interaction.
    """
    data, error = rpc_client.get_course_contents("AOS", "202401")
    if error or not data:
        _print_error(error or "No materials to display.")
        return None, False

    contents = json.loads(data).get("contents", [])
    if not contents:
        _print_error("No materials to display.")
        return None, False

    index_map = {}
    for i, item in enumerate(contents, start=1):
        index_map[i] = item
        print(f"{i}. {item['name']}")

    try:
        choice = int(input("Enter number to download (0 to go back): "))
    except ValueError:
        return None, False

    if choice == 0 or choice not in index_map:
        return None, False

    material_id = index_map[choice]["id"]
    data_bytes, filename, err = rpc_client.get_course_material("AOS", "20241", material_id)
    if err:
        _print_error(err)
    else:
        downloads_dir = os.path.join(os.getcwd(), "Downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        with open(os.path.join(downloads_dir, filename), "wb") as fh:
            fh.write(data_bytes)
        print(f"Downloaded: {filename}")
    return None, False


def _fetch_and_display_queries(allow_answer: bool = False):
    """
    Fetch and display all course queries.

    If *allow_answer* is True (faculty mode), prompts the user to answer one.
    """
    result, error = rpc_client.get_queries("AOS", "20241")
    if error:
        _print_error(error)
        return None, False

    query_list = json.loads(result).get("q", [])
    query_index: dict = {}

    if not query_list:
        print("No queries found.")
        return None, False

    print("Queries:")
    for i, q in enumerate(query_list, start=1):
        query_index[i] = q["id"]
        print(f"[{i}] [{q['posted_by']}] → {q['query_text']}")
        if q.get("reply"):
            print(f"    Answered by [{q.get('replied_by', 'unknown')}]: {q['reply']}")
        else:
            print("    (unanswered)")
        print("    " + "-" * 40)

    if not allow_answer:
        return None, False

    try:
        choice = int(input("Enter number to answer a query (0 to go back): "))
    except ValueError:
        return None, False

    if choice == 0 or choice not in query_index:
        return None, False

    answer_text = input("Enter your answer: ")
    err = answer_query(query_index[choice], answer_text)
    if err:
        _print_error(err)
    else:
        print("Answer submitted.")
    return None, False


def _chat_with_llm():
    """Start a chat session with the AI tutor."""
    error = chat_with_tutor()
    if error:
        _print_error(error)
    return None, False


# ---------------------------------------------------------------------------
# Student menu actions
# ---------------------------------------------------------------------------

def student_course_contents():
    return _fetch_and_display_course_contents()


def student_submit_assignment():
    assignment_name = input("Assignment name: ")
    path = input("Path to file: ")
    if not os.path.exists(path):
        _print_error("File not found.")
        return None, False
    filename = os.path.split(path)[1]
    error = rpc_client.submit_assignment(path, assignment_name, filename)
    if error:
        _print_error(error)
    else:
        print("Assignment submitted successfully.")
    return None, False


def student_get_queries():
    return _fetch_and_display_queries(allow_answer=False)


def student_create_query():
    query_text = input("Enter your query: ")
    error = rpc_client.create_query("AOS", query_text)
    if error:
        _print_error(error)
    else:
        print("Query submitted successfully.")
    return None, False


STUDENT_MENU_OPTIONS = (
    (1, "Course Contents"),
    (2, "Submit Assignment"),
    (3, "View Queries"),
    (4, "Post a Query"),
    (5, "Chat with AI Tutor"),
)

STUDENT_MENU_ACTIONS = {
    1: student_course_contents,
    2: student_submit_assignment,
    3: student_get_queries,
    4: student_create_query,
    5: _chat_with_llm,
}


# ---------------------------------------------------------------------------
# Faculty menu actions
# ---------------------------------------------------------------------------

def faculty_course_contents():
    return _fetch_and_display_course_contents()


def faculty_get_assignments():
    print("Downloading all assignment submissions...")
    course = "AOS"
    assignment_name = "Assignment 1"
    file_data, error = rpc_client.get_submitted_assignments(course, assignment_name)
    if error:
        _print_error(error)
        return None, False
    path = os.path.join(os.getcwd(), "Downloads", course, assignment_name)
    os.makedirs(path, exist_ok=True)
    zip_path = os.path.join(path, f"{assignment_name}.zip")
    with open(zip_path, "wb") as fh:
        fh.write(file_data)
    print(f"Assignments downloaded to: {zip_path}")
    return None, False


def faculty_upload_material():
    material_name = input("Material name: ")
    path = input("Path to file: ")
    if not os.path.exists(path):
        _print_error("File not found.")
        return None, False
    error = rpc_client.upload_material(path, material_name)
    if error:
        _print_error(error)
    else:
        print("Material uploaded successfully.")
    return None, False


def faculty_get_queries():
    return _fetch_and_display_queries(allow_answer=True)


FACULTY_MENU_OPTIONS = (
    (1, "Course Contents"),
    (2, "Download Assignment Submissions"),
    (3, "Upload Course Material"),
    (4, "View & Answer Queries"),
    (5, "Chat with AI Tutor"),
)

FACULTY_MENU_ACTIONS = {
    1: faculty_course_contents,
    2: faculty_get_assignments,
    3: faculty_upload_material,
    4: faculty_get_queries,
    5: _chat_with_llm,
}
