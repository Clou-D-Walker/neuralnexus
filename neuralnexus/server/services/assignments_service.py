"""
services/assignments_service.py
--------------------------------
gRPC servicer for NeuralNexus assignment submission and retrieval.
"""

import base64
import os
import sqlite3
from io import BytesIO

DB_PATH: str = os.environ.get("DB_PATH", "lms.db")

from proto import Lms_pb2, Lms_pb2_grpc
from consensus.raft_node import node
from handlers.assignments_handler import submit_assignment, get_all_submissions
from security.access_control import faculty_access_token_required, student_access_token_required


def _stream_bytes(data: bytes):
    """Yield GetSubmittedAssignmentsResponse messages in 1 MB chunks."""
    buf = BytesIO(data)
    chunk_size = 1024 * 1024
    while chunk := buf.read(chunk_size):
        yield Lms_pb2.GetSubmittedAssignmentsResponse(data=chunk, code="200")


class AssignmentsService(Lms_pb2_grpc.AssignmentsServicer):
    """Handles assignment submission and retrieval RPCs."""

    @student_access_token_required
    def submitAssignment(self, request_iterator, context, **kwargs):
        try:
            data = b""
            course = filename = assignment_name = None
            student_id = kwargs["userid"]

            for req in request_iterator:
                data += req.data
                course = req.course
                filename = req.filename
                assignment_name = req.assignment_name

            if not data:
                return Lms_pb2.SubmitAssignmentResponse(error="Empty file", code="400")

            with sqlite3.connect(DB_PATH) as conn:
                raft_args = {
                    "conn": "conn",
                    "course_id": course,
                    "assignment_id": assignment_name,
                    "filename": filename,
                    "data": base64.b64encode(data).decode("utf-8"),
                    "student_id": student_id,
                }
                replicated = node.leader_append_log("assignments.submit_assignment", raft_args)
                if not replicated:
                    return Lms_pb2.SubmitAssignmentResponse(
                        error="Majority of nodes are down", code="500"
                    )
                error = submit_assignment(conn, student_id, course, assignment_name, data, filename)

            if error:
                return Lms_pb2.SubmitAssignmentResponse(error=str(error), code="400")
            return Lms_pb2.SubmitAssignmentResponse(code="200")
        except Exception as exc:
            print(exc)
            return Lms_pb2.SubmitAssignmentResponse(error=str(exc), code="400")

    @faculty_access_token_required
    def getSubmittedAssignment(self, request, context, **kwargs):
        try:
            assignment_name = request.assignment_name
            course = request.course
            data, error = get_all_submissions(course, assignment_name)
            if error:
                yield Lms_pb2.GetSubmittedAssignmentsResponse(error=str(error), code="400")
                return
            for chunk in _stream_bytes(data):
                yield chunk
        except Exception as exc:
            yield Lms_pb2.GetSubmittedAssignmentsResponse(error=str(exc), code="500")
