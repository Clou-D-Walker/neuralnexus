"""
database/schema.py
------------------
SQLite schema creation and initial setup for NeuralNexus.

Call `create_everything()` on first run to initialise all required tables.
"""

import sqlite3
import os

DB_PATH: str = os.environ.get("DB_PATH", "lms.db")


# ---------------------------------------------------------------------------
# Individual table creators
# ---------------------------------------------------------------------------

def _create_roles(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id   uuid PRIMARY KEY,
            name text
        )
    """)


def _create_users(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         uuid,
            username   text,
            password   text,
            email      text,
            phone      text,
            role_id    uuid,
            created_at timestamp,
            PRIMARY KEY (id),
            FOREIGN KEY (role_id) REFERENCES roles
        )
    """)


def _create_courses(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id            uuid,
            course_name   text,
            course_code   text,
            instructor_id uuid,
            created_at    timestamp,
            PRIMARY KEY (id),
            FOREIGN KEY (instructor_id) REFERENCES users
        )
    """)


def _create_course_enrolled(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS course_enrolled (
            course_id  uuid,
            user_id    uuid,
            created_at timestamp,
            PRIMARY KEY (course_id, user_id),
            FOREIGN KEY (course_id) REFERENCES courses,
            FOREIGN KEY (user_id)   REFERENCES users
        )
    """)


def _create_assignments(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id          uuid,
            name        text,
            due_date    timestamp,
            description text,
            course_id   uuid,
            created_at  timestamp,
            PRIMARY KEY (id),
            FOREIGN KEY (course_id) REFERENCES courses
        )
    """)


def _create_assignment_submissions(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assignment_submissions (
            assignment_id uuid,
            user_id       uuid,
            filename      text,
            created_at    timestamp,
            PRIMARY KEY (assignment_id, user_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments,
            FOREIGN KEY (user_id)       REFERENCES users
        )
    """)


def _create_materials(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id         uuid,
            name       text,
            course_id  uuid,
            file_name  text,
            created_at timestamp,
            PRIMARY KEY (id),
            FOREIGN KEY (course_id) REFERENCES courses
        )
    """)


def _create_queries(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id         uuid,
            query_text text,
            posted_by  uuid,
            reply_by   uuid,
            created_at timestamp,
            course_id  uuid NOT NULL,
            reply      text,
            PRIMARY KEY (id),
            FOREIGN KEY (posted_by)  REFERENCES users,
            FOREIGN KEY (course_id)  REFERENCES courses,
            FOREIGN KEY (reply_by)   REFERENCES users
        )
    """)


def _create_node_discovery(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS node_discovery (
            id         uuid PRIMARY KEY,
            host       text,
            port       text,
            created_at timestamp,
            is_leader  boolean DEFAULT false
        )
    """)


def _create_state_info(cur: sqlite3.Cursor) -> None:
    """
    Persistent Raft state for this node: current term, log index, and voted_for.
    Exactly one row should exist; seeded on first creation.
    """
    cur.execute("""
        CREATE TABLE IF NOT EXISTS state_info (
            term      integer DEFAULT 0,
            idx       integer DEFAULT 0,
            voted_for text
        )
    """)
    # Seed one row if the table is empty
    cur.execute("SELECT COUNT(*) FROM state_info")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO state_info(term, idx, voted_for) VALUES(0, 0, NULL)")


def _create_raft_logs(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS raft_logs (
            id         uuid PRIMARY KEY,
            operation  text,
            args       text,
            term       integer,
            idx        integer,
            commited   boolean,
            created_at timestamp,
            UNIQUE (idx, term)
        )
    """)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_everything() -> None:
    """
    Initialise all NeuralNexus database tables.

    Safe to call on a database that already exists – all statements use
    CREATE TABLE IF NOT EXISTS.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            _create_roles(cur)
            _create_users(cur)
            _create_courses(cur)
            _create_assignments(cur)
            _create_course_enrolled(cur)
            _create_assignment_submissions(cur)
            _create_materials(cur)
            _create_queries(cur)
            _create_node_discovery(cur)
            _create_raft_logs(cur)
            _create_state_info(cur)
            conn.commit()
            cur.close()
    except Exception as exc:
        print(f"[database.schema] Error during schema initialisation: {exc}")
