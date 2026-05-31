"""
handlers/materials_handler.py
------------------------------
Business logic for course-material storage and retrieval in NeuralNexus.
"""

import os
import sqlite3
from io import BytesIO
from typing import Optional, Tuple

from database.db_methods import add_material, get_course_materials, get_material


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

def _write_file(directory: str, filename: str, data: bytes) -> Optional[Exception]:
    """Write *data* to *directory/filename*, creating the directory if needed."""
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

def upload_material(
    conn: sqlite3.Connection,
    course_id: str,
    data: bytes,
    filename: str,
    name: str,
) -> Optional[Exception]:
    """
    Persist a course material to the database and file-system.

    Files are stored at:  Resources/<course_id>/<filename>
    """
    try:
        directory = os.path.join(os.getcwd(), "Resources", course_id)
        error = add_material(conn, course_id, name, filename)
        if error:
            conn.rollback()
            return error
        error = _write_file(directory, filename, data)
        if error:
            conn.rollback()
            return error
        conn.commit()
        return None
    except Exception as exc:
        return exc


# Legacy alias referenced by the Raft dispatch table
upload = upload_material


def get_course_contents(
    conn: sqlite3.Connection,
    course_name: str,
) -> Tuple[Optional[dict], Optional[Exception]]:
    """Return a dict ``{"contents": [...]}`` for a course, or an error."""
    try:
        contents, error = get_course_materials(conn, course_name)
        if contents:
            return {"contents": [{"id": r[0], "name": r[1], "file": r[2]} for r in contents]}, error
        return {"contents": []}, error
    except Exception as exc:
        return None, exc


def get_course_material(
    conn: sqlite3.Connection,
    course: str,
    material_id: str,
) -> Tuple[Optional[BytesIO], Optional[str], Optional[str], Optional[str]]:
    """
    Look up a material by ID and return its file data as a BytesIO buffer.

    Returns (buffer, name, filename, error).
    """
    try:
        material, error = get_material(conn, material_id)
        if not material:
            return None, None, None, "Material not found"
        path = os.path.join(os.getcwd(), "Resources", material[2], material[1])
        if not os.path.exists(path):
            return None, None, None, "File not found"
        buf = BytesIO()
        with open(path, "rb") as fh:
            buf.write(fh.read())
        buf.seek(0)
        return buf, material[0], material[1], None
    except Exception as exc:
        return None, None, None, str(exc)


# ---------------------------------------------------------------------------
# Raft operation dispatch table
# ---------------------------------------------------------------------------

materials_map = {
    "material_upload": upload_material,
    # Legacy key kept so existing Raft logs still apply correctly
    "upload_material": upload_material,
}
