"""
services/auth_service.py
------------------------
gRPC servicer for NeuralNexus authentication endpoints.
"""

import grpc

from proto import Lms_pb2, Lms_pb2_grpc
from handlers.auth_handler import login


class AuthService(Lms_pb2_grpc.AuthServicer):
    """Handles student and faculty login RPCs."""

    def studentLogin(self, request, context):
        try:
            token, error = login(request.username, request.password, "Student")
            if error:
                return Lms_pb2.LoginResponse(error="Invalid email or password", code="401")
            return Lms_pb2.LoginResponse(token=token, code="200")
        except Exception as exc:
            return Lms_pb2.LoginResponse(error="Internal Server Error", code="500")

    def facultyLogin(self, request, context):
        try:
            token, error = login(request.username, request.password, "Instructor")
            if error:
                return Lms_pb2.LoginResponse(error="Invalid email or password", code="401")
            return Lms_pb2.LoginResponse(token=token, code="200")
        except Exception as exc:
            print(exc)
            return Lms_pb2.LoginResponse(error="Internal Server Error", code="500")
