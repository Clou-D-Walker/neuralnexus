"""
server_entry.py
---------------
NeuralNexus gRPC server entry point.

Starts all service servicers on the configured port and launches the
Raft consensus timer.

Usage (from the server/ directory with the virtual environment activated):
    python server_entry.py
"""

import logging
import os
from concurrent import futures

import grpc

from proto import Lms_pb2_grpc
from database.schema import create_everything
from services.auth_service import AuthService
from services.materials_service import MaterialsService
from services.assignments_service import AssignmentsService
from services.queries_service import QueryService
from services.llm_service import LlmService
from services.raft_service import RaftService
from consensus.raft_node import timer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("neuralnexus.server")

# Port is read from the NODE_PORT environment variable, defaulting to 50052.
SERVER_PORT = os.environ.get("NODE_PORT", "50052")
MAX_WORKERS = 4


def serve() -> None:
    """Configure and start the NeuralNexus gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKERS))

    Lms_pb2_grpc.add_AuthServicer_to_server(AuthService(), server)
    Lms_pb2_grpc.add_MaterialsServicer_to_server(MaterialsService(), server)
    Lms_pb2_grpc.add_AssignmentsServicer_to_server(AssignmentsService(), server)
    Lms_pb2_grpc.add_QueriesServicer_to_server(QueryService(), server)
    Lms_pb2_grpc.add_LlmServicer_to_server(LlmService(), server)
    Lms_pb2_grpc.add_RaftServicer_to_server(RaftService(), server)

    server.add_insecure_port(f"[::]:{SERVER_PORT}")
    server.start()
    logger.info("NeuralNexus server started on port %s", SERVER_PORT)
    print(f"[NeuralNexus] Server listening on port {SERVER_PORT}")

    timer.start()
    server.wait_for_termination()


if __name__ == "__main__":
    create_everything()
    serve()
