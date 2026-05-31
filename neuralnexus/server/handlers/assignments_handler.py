"""
handlers/assignments_handler.py
--------------------------------
Business logic for assignment submission and retrieval in NeuralNexus.
"""

import base64
import os
import sqlite3
from typing import Optional, Tuple

from core.utils import zip_files_in_directory
from database.db_methods import (
    insert_assignment,
    insert_assignment_submission,
    select_assignments,
)


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

def _write_file(directory: str, filename: str, data) -> Optional[Exception]:
    """
    Write *data* to *directory/filename*.

    If *data* is a base64-encoded string (as stored in Raft logs), it is
    decoded to bytes first.
    """
    if isinstance(data, str):
        data = base64.b64decode(data.encode())
    try:
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, filename), "wb") as fh:
            fh.write(data)
        return None
    except Exception as exc:
        return exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_assignment(
    conn: sqlite3.Connection,
    name: str,
    due_date: str,
    description: str,
    course_id: str,
) -> Optional[Exception]:
    """Create a new assignment definition."""
    try:
        return insert_assignment(conn, name, due_date, description, course_id)
    except Exception as exc:
        return exc


def get_assignments(
    conn: sqlite3.Connection,
    course: str,
):
    """Return all assignments for a course."""
    return select_assignments(conn, course)


def submit_assignment(
    conn: sqlite3.Connection,
    student_id: str,
    course_id: str,
    assignment_id: str,
    data,
    filename: str,
) -> Optional[Exception]:
    """
    Persist a student assignment submission to the database and file-system.

    Files are stored at:  Resources/<course_id>/<assignment_id>/<student_id>-<filename>
    """
    try:
        new_filename = f"{student_id}-{filename}"
        error = insert_assignment_submission(conn, assignment_id, student_id, new_filename)
        if error:
            return error
        directory = os.path.join(os.getcwd(), "Resources", course_id, assignment_id)
        error = _write_file(directory, new_filename, data)
        if error:
            conn.rollback()
            return error
        conn.commit()
        return None
    except Exception as exc:
        return exc


def get_all_submissions(
    course: str,
    assignment_name: str,
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Return all submission files for an assignment as a ZIP archive (bytes).
    """
    try:
        path = os.path.join(os.getcwd(), "Resources", course, assignment_name)
        if not os.path.exists(path):
            return None, "Assignment Not Found"
        return zip_files_in_directory(path), None
    except Exception as exc:
        return None, str(exc)


# Legacy alias used by Services layer
get_all_assignments = get_all_submissions


# ---------------------------------------------------------------------------
# Raft operation dispatch table
# ---------------------------------------------------------------------------

assignments_map = {
    "submit_assignment": submit_assignment,
    "create_assignment": create_assignment,
}
