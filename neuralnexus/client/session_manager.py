"""
session_manager.py
------------------
GrpcHelper – a singleton registry holding all active gRPC service stubs
and the current user's session token for NeuralNexus client sessions.
"""


class GrpcHelper:
    """Holds gRPC stubs and the active session token for a connected NeuralNexus session."""

    def __init__(self) -> None:
        self.auth_stub = None
        self.materials_stub = None
        self.assignment_stub = None
        self.queries_stub = None
        self.llm_stub = None
        self.access_token: str | None = None

    def set_auth_stub(self, stub) -> None:
        self.auth_stub = stub

    def set_materials_stub(self, stub) -> None:
        self.materials_stub = stub

    def set_assignment_stub(self, stub) -> None:
        self.assignment_stub = stub

    def set_queries_stub(self, stub) -> None:
        self.queries_stub = stub

    def set_llm_stub(self, stub) -> None:
        self.llm_stub = stub

    def set_access_token(self, token: str | None) -> None:
        self.access_token = token


# Module-level singleton – import this wherever stubs are needed
grpc_helper = GrpcHelper()
