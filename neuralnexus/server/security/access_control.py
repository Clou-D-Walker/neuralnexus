"""
security/access_control.py
--------------------------
gRPC method decorators that enforce role-based access control for
NeuralNexus service endpoints.

Each decorator reads the 'authorization' metadata key, decrypts the
AES session token, validates the role and expiry, then injects
``kwargs["userid"]`` into the wrapped function.
"""

from functools import wraps

import grpc

from security.token_manager import session_manager
from core.utils import get_timestamp


def student_access_token_required(f):
    """Allow only authenticated Students to call the decorated RPC method."""

    @wraps(f)
    def _decorator(self, request_iterator, context, *args, **kwargs):
        for key, value in context.invocation_metadata():
            if key == "authorization":
                try:
                    payload = session_manager.decrypt(value)
                    user_id, role, expiry = payload.split("|")
                    if role != "Student":
                        context.abort(grpc.StatusCode.PERMISSION_DENIED, "Access Restricted")
                    if expiry < get_timestamp():
                        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Session Expired")
                except Exception:
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid Token")
                kwargs["userid"] = user_id
                return f(self, request_iterator, context, *args, **kwargs)
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token is Missing")

    return _decorator


def faculty_access_token_required(f):
    """Allow only authenticated Instructors to call the decorated RPC method."""

    @wraps(f)
    def _decorator(self, request_iterator, context, *args, **kwargs):
        for key, value in context.invocation_metadata():
            if key == "authorization":
                try:
                    payload = session_manager.decrypt(value)
                    user_id, role, expiry = payload.split("|")
                    if role != "Instructor":
                        context.abort(grpc.StatusCode.PERMISSION_DENIED, "Access Restricted")
                    if expiry < get_timestamp():
                        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Session Expired")
                except Exception:
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid Token")
                kwargs["userid"] = user_id
                return f(self, request_iterator, context, *args, **kwargs)
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token is Missing")

    return _decorator


def any_access_token_required(f):
    """Allow any authenticated user (Student or Instructor) to call the decorated RPC method."""

    @wraps(f)
    def _decorator(self, request_iterator, context, *args, **kwargs):
        for key, value in context.invocation_metadata():
            if key == "authorization":
                try:
                    payload = session_manager.decrypt(value)
                    user_id, _, expiry = payload.split("|")
                    if expiry < get_timestamp():
                        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Session Expired")
                except Exception:
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid Token")
                kwargs["userid"] = user_id
                return f(self, request_iterator, context, *args, **kwargs)
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token is Missing")

    return _decorator
