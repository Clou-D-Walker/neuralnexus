"""
database/db_methods.py
----------------------
Raw SQL query functions for all NeuralNexus entities.

All functions accept an open sqlite3.Connection as their first argument so
callers retain transaction control.
"""

import json
import sqlite3
import uuid
from typing import Optional, Tuple, Any, List


def gen_uuid() -> str:
    """Generate a new random UUID string."""
    return str(uuid.uuid4())


def _dict_row_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# Users / Auth
# ---------------------------------------------------------------------------

def validate_user(
    conn: sqlite3.Connection,
    user: str,
    password: str,
    role: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate login credentials against the database.

    Returns (is_valid, courses_placeholder, user_id).
    """
    query = """
        SELECT u.id
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.id
        WHERE (email = ? OR username = ?)
          AND password = ?
          AND r.name = ?
        LIMIT 1
    """
    cursor = conn.cursor()
    cursor.execute(query, (user, user, password, role))
    row = cursor.fetchone()
    if row is None:
        return False, None, None
    return True, "AOS", row[0]


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def add_material(
    conn: sqlite3.Connection,
    course_id: str,
    name: str,
    filename: str,
) -> Optional[Exception]:
    """Insert a material record. Returns an exception on failure, else None."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO materials(id, name, course_id, file_name, created_at) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (gen_uuid(), name, course_id, filename),
        )
    except Exception as exc:
        conn.rollback()
        return exc
    return None


def get_course_materials(
    conn: sqlite3.Connection,
    course_id: str,
) -> Tuple[Optional[List], Optional[Exception]]:
    """Return all materials for a given course."""
    try:
        query = """
            SELECT m.id AS material_id, m.name AS material_name, m.file_name AS filename
            FROM materials m
            WHERE m.course_id = ?
        """
        cursor = conn.cursor()
        cursor.execute(query, (course_id,))
        return cursor.fetchall(), None
    except Exception as exc:
        return None, exc


def get_material(
    conn: sqlite3.Connection,
    material_id: str,
) -> Tuple[Optional[tuple], Optional[Exception]]:
    """Return (name, file_name, course_id) for a material by ID."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT m.name, m.file_name, m.course_id FROM materials m WHERE m.id = ?",
            (material_id,),
        )
        return cursor.fetchone(), None
    except Exception as exc:
        return None, exc


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

def insert_assignment(
    conn: sqlite3.Connection,
    name: str,
    due_date: str,
    description: str,
    course_id: str,
) -> Optional[Exception]:
    """Insert an assignment definition. Returns None on success."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO assignments(id, name, due_date, description, course_id, created_at) "
            "VALUES(?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (gen_uuid(), name, due_date, description, course_id),
        )
        conn.commit()
        return None
    except Exception as exc:
        conn.rollback()
        return exc


def insert_assignment_submission(
    conn: sqlite3.Connection,
    assignment_id: str,
    student_id: str,
    filename: str,
) -> Optional[Exception]:
    """Insert or replace an assignment submission record."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO assignment_submissions"
            "(assignment_id, user_id, filename, created_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (assignment_id, student_id, filename),
        )
        return None
    except Exception as exc:
        conn.rollback()
        return exc


def select_assignments(
    conn: sqlite3.Connection,
    course_id: str,
) -> Tuple[Optional[List[dict]], Optional[Exception]]:
    """Return all assignments for a course as a list of dicts."""
    try:
        columns = ("id", "name", "due_date", "description")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, due_date, description FROM assignments WHERE course_id = ?",
            (course_id,),
        )
        rows = cursor.fetchall()
        return [{columns[i]: row[i] for i in range(len(row))} for row in rows], None
    except Exception as exc:
        return None, exc


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def insert_query(
    conn: sqlite3.Connection,
    query_text: str,
    posted_by: str,
    course_id: str,
) -> Optional[Exception]:
    """Insert a new student query. Returns None on success."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO queries(id, query_text, posted_by, course_id, created_at) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (gen_uuid(), query_text, posted_by, course_id),
        )
        conn.commit()
        return None
    except Exception as exc:
        return exc


def select_queries(
    conn: sqlite3.Connection,
    course_id: str,
) -> Tuple[Optional[List[dict]], Optional[Exception]]:
    """Return all queries for a course, joined with poster and answerer usernames."""
    try:
        conn.row_factory = _dict_row_factory
        query = """
            SELECT ques.id,
                   ques.query_text,
                   ques.posted_by,
                   ques.reply,
                   u2.username AS replied_by
            FROM (
                SELECT queries.id,
                       query_text,
                       users.username AS posted_by,
                       reply,
                       reply_by,
                       course_id
                FROM queries
                LEFT JOIN users ON posted_by = users.id
                WHERE course_id = ?
            ) AS ques
            LEFT JOIN users u2 ON u2.id = ques.reply_by
        """
        cursor = conn.cursor()
        cursor.execute(query, (course_id,))
        conn.commit()
        return cursor.fetchall(), None
    except Exception as exc:
        return None, exc


def update_answer_to_query(
    conn: sqlite3.Connection,
    query_id: str,
    answer: str,
    userid: str,
) -> Optional[Exception]:
    """Update the reply and replier on an existing query."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE queries SET reply = ?, reply_by = ? WHERE id = ?",
            (answer, userid, query_id),
        )
        conn.commit()
        return None
    except Exception as exc:
        return exc
