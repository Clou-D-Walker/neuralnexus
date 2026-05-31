"""
services/materials_service.py
------------------------------
gRPC servicer for NeuralNexus course-material operations.
"""

import sys
import json
import os
import sqlite3

DB_PATH: str = os.environ.get("DB_PATH", "lms.db")

from proto import Lms_pb2, Lms_pb2_grpc
from consensus.raft_node import node
from handlers.materials_handler import upload_material, get_course_contents, get_course_material
from security.access_control import faculty_access_token_required, any_access_token_required


def _stream_file_chunks(name: str, filename: str, data):
    """Yield GetCourseMaterialResponse messages in 1 MB chunks."""
    chunk_size = 1024 * 1024
    while chunk := data.read(chunk_size):
        yield Lms_pb2.GetCourseMaterialResponse(name=name, filename=filename, data=chunk)


class MaterialsService(Lms_pb2_grpc.MaterialsServicer):
    """Handles course material upload and retrieval RPCs."""

    @faculty_access_token_required
    def courseMaterialUpload(self, request_iterator, context, **kwargs):
        try:
            data = b""
            course = filename = name = None
            req_count = 0

            for req in request_iterator:
                req_count += 1
                data += req.data
                course = req.course
                filename = req.filename
                name = req.name

            if req_count == 0:
                return Lms_pb2.UploadCourseMaterialResponse(size="0", code="200")

            with sqlite3.connect(DB_PATH) as conn:
                raft_args = {
                    "conn": "conn",
                    "course_id": course,
                    "filename": filename,
                    "data": data,
                    "name": name,
                }
                replicated = node.leader_append_log("materials.material_upload", raft_args)
                if not replicated:
                    return Lms_pb2.UploadCourseMaterialResponse(
                        error="Majority of nodes are down", code="500"
                    )
                error = upload_material(conn, course, data, filename, name)

            if error:
                return Lms_pb2.UploadCourseMaterialResponse(error=str(error), code="400")
            return Lms_pb2.UploadCourseMaterialResponse(
                size=str(sys.getsizeof(data)), code="200"
            )
        except Exception as exc:
            return Lms_pb2.UploadCourseMaterialResponse(error=str(exc), code="500")

    @any_access_token_required
    def getCourseContents(self, request, context, **kwargs):
        course = request.course
        with sqlite3.connect(DB_PATH) as conn:
            contents, error = get_course_contents(conn, course)
        if error:
            return Lms_pb2.GetCourseContentsResponse(course=course, error=str(error))
        return Lms_pb2.GetCourseContentsResponse(
            course=course, data=json.dumps(contents)
        )

    @any_access_token_required
    def getCourseMaterial(self, request, context, **kwargs):
        try:
            course = request.course
            material_id = request.name
            with sqlite3.connect(DB_PATH) as conn:
                data, name, filename, error = get_course_material(conn, course, material_id)
            if error:
                yield Lms_pb2.GetCourseMaterialResponse(error=error)
                return
            for chunk in _stream_file_chunks(name, filename, data):
                yield chunk
        except Exception as exc:
            yield Lms_pb2.GetCourseMaterialResponse(error=str(exc))
