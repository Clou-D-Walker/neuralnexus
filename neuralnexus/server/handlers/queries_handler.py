"""
handlers/queries_handler.py
----------------------------
Business logic for student Q&A queries in NeuralNexus.
"""

import sqlite3
from typing import Optional, Tuple, List

from database.db_methods import insert_query, select_queries, update_answer_to_query


def create_query(
    conn: sqlite3.Connection,
    course: str,
    query: str,
    user_id: str,
) -> Optional[Exception]:
    """Insert a new student query. Returns None on success."""
    error = insert_query(conn, query, user_id, course)
    return error if error else None


def answer_query(
    conn: sqlite3.Connection,
    queryid: str,
    answer: str,
    user_id: str,
) -> Optional[Exception]:
    """Record an instructor's answer to a query."""
    return update_answer_to_query(conn, queryid, answer, user_id)


def get_queries(
    conn: sqlite3.Connection,
    course_id: str,
) -> Tuple[Optional[List], Optional[Exception]]:
    """Return all queries for a course."""
    try:
        return select_queries(conn, course_id)
    except Exception as exc:
        return None, exc


# ---------------------------------------------------------------------------
# Raft operation dispatch table
# ---------------------------------------------------------------------------

query_map = {
    "create_query": create_query,
    "answer_query": answer_query,
}
