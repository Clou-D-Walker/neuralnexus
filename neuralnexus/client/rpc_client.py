"""
rpc_client.py
-------------
All gRPC transport functions for the NeuralNexus client.

This module handles:
- Raft leader discovery across bootstrap nodes
- Stub creation / reconnection
- All service RPC calls (auth, materials, assignments, queries, LLM)
"""

import os
import time
import grpc
from datetime import datetime

import Lms_pb2
import Lms_pb2_grpc
from session_manager import grpc_helper

# ---------------------------------------------------------------------------
# Cluster configuration
# ---------------------------------------------------------------------------

COURSE_ID = "8d313659-2360-44a2-9ab0-57dbd1ddc201"
ASSIGNMENT_ID = "2d8f2298-beac-4a27-b70a-c1da56600993"
LEADER_RETRY_DELAY = 2  # seconds between leader-discovery retries

BOOTSTRAP_NODES = [
    {"id": "ee1f954b-99ab-48e2-95fd-730e4aec2489", "host": "localhost", "port": "50052"},
    {"id": "de3b3357-8c1f-4911-910e-977d2ff02611", "host": "localhost", "port": "50053"},
    {"id": "becedead-63a4-48a8-a017-e284cd02d21e", "host": "localhost", "port": "50054"},
    {"id": "600474f3-0a8f-4ed6-ba56-d9576ddcdb63", "host": "localhost", "port": "50055"},
]


# ---------------------------------------------------------------------------
# Leader discovery
# ---------------------------------------------------------------------------

def get_leader_id() -> str | None:
    """
    Poll each bootstrap node via getLeader RPC.

    Returns the leader's node UUID, or None if no leader is found.
    """
    for node in BOOTSTRAP_NODES:
        address = f"{node['host']}:{node['port']}"
        print(f"[NeuralNexus] Querying bootstrap node: {address}")
        try:
            with grpc.insecure_channel(address) as channel:
                stub = Lms_pb2_grpc.RaftStub(channel)
                response = stub.getLeader(Lms_pb2.GetLeaderRequest(ack=1))
                if response.node_id:
                    print(f"[NeuralNexus] Leader found: {response.node_id} (via {address})")
                    return response.node_id
        except grpc.RpcError as exc:
            print(f"[NeuralNexus] Could not reach {address}: {exc}")
    return None


def get_leader_host_port(leader_id: str) -> tuple[str | None, str | None]:
    """Map a leader UUID to its host and port from the bootstrap list."""
    for node in BOOTSTRAP_NODES:
        if node["id"] == leader_id:
            return node["host"], node["port"]
    return None, None


def connect_to_leader(host: str, port: str) -> grpc.Channel | None:
    """
    Create gRPC stubs for all services and store them in ``grpc_helper``.

    Returns the underlying channel on success, or None on failure.
    """
    try:
        address = f"{host}:{port}"
        channel = grpc.insecure_channel(address)
        grpc_helper.set_auth_stub(Lms_pb2_grpc.AuthStub(channel))
        grpc_helper.set_assignment_stub(Lms_pb2_grpc.AssignmentsStub(channel))
        grpc_helper.set_materials_stub(Lms_pb2_grpc.MaterialsStub(channel))
        grpc_helper.set_queries_stub(Lms_pb2_grpc.QueriesStub(channel))
        grpc_helper.set_llm_stub(Lms_pb2_grpc.LlmStub(channel))
        print(f"[NeuralNexus] Connected to leader at {address}")
        return channel
    except grpc.RpcError as exc:
        print(f"[NeuralNexus] Failed to connect to leader: {exc}")
        return None


def reconnect_to_leader() -> None:
    """Discover a new leader and reconnect all stubs (called on UNAVAILABLE errors)."""
    time.sleep(LEADER_RETRY_DELAY)
    leader_id = get_leader_id()
    if leader_id:
        host, port = get_leader_host_port(leader_id)
        if host and port:
            connect_to_leader(host, port)


# ---------------------------------------------------------------------------
# Auth RPCs
# ---------------------------------------------------------------------------

def student_login(username: str, password: str) -> tuple[str | None, str | None]:
    """Authenticate as a student. Returns (token, error)."""
    try:
        response = grpc_helper.auth_stub.studentLogin(
            Lms_pb2.LoginRequest(username=username, password=password)
        )
        if response.code == "200":
            return response.token, None
        return None, response.error
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return None, exc


def faculty_login(username: str, password: str) -> tuple[str | None, str | None]:
    """Authenticate as a faculty member. Returns (token, error)."""
    try:
        response = grpc_helper.auth_stub.facultyLogin(
            Lms_pb2.LoginRequest(username=username, password=password)
        )
        if response.code == "200":
            return response.token, None
        return None, response.error
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return None, exc


# ---------------------------------------------------------------------------
# Materials RPCs
# ---------------------------------------------------------------------------

def get_course_contents(course: str, term: str) -> tuple[str | None, str | None]:
    """Return the JSON-encoded list of course materials, or (None, error)."""
    try:
        response = grpc_helper.materials_stub.getCourseContents(
            Lms_pb2.GetCourseContentsRequest(course=COURSE_ID, term=term),
            metadata=(("authorization", grpc_helper.access_token),),
        )
        if not response.error:
            return response.data, None
        return None, response.error
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return None, exc


def get_course_material(course: str, term: str, material_id: str) -> tuple:
    """Download a course material. Returns (data_bytes, filename, error)."""
    try:
        data = b""
        filename = None
        error = None
        for chunk in grpc_helper.materials_stub.getCourseMaterial(
            Lms_pb2.GetCourseMaterialRequest(course=COURSE_ID, term=term, name=material_id),
            metadata=(("authorization", grpc_helper.access_token),),
        ):
            data += chunk.data
            filename = chunk.filename
            error = chunk.error
        if not error:
            return data, filename, None
        return None, None, error
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return None, None, exc.details()


def _material_upload_chunks(path: str, filename: str, material_name: str):
    """Generator yielding 1 MB upload chunks for a material file."""
    block_size = 1024 * 1024
    with open(path, "rb") as fh:
        while chunk := fh.read(block_size):
            yield Lms_pb2.UploadCourseMaterialRequest(
                course=COURSE_ID,
                term="20241",
                filename=filename,
                data=chunk,
                created=str(datetime.now()),
                name=material_name,
            )


def upload_material(path: str, name: str) -> str | None:
    """Upload a course material file. Returns error string or None on success."""
    filename = os.path.split(path)[1]
    try:
        response = grpc_helper.materials_stub.courseMaterialUpload(
            _material_upload_chunks(path, filename, name),
            metadata=(("authorization", grpc_helper.access_token),),
        )
        if not response.error:
            return None
        return response.error
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return exc.details()


# ---------------------------------------------------------------------------
# Assignments RPCs
# ---------------------------------------------------------------------------

def _assignment_upload_chunks(path: str, filename: str, assignment_name: str):
    """Generator yielding 1 MB upload chunks for an assignment file."""
    block_size = 1024 * 1024
    with open(path, "rb") as fh:
        while chunk := fh.read(block_size):
            yield Lms_pb2.SubmitAssignmentRequest(
                course=COURSE_ID,
                assignment_name=ASSIGNMENT_ID,
                data=chunk,
                filename=filename,
            )


def submit_assignment(
    assignment_file: str,
    assignment_name: str,
    filename: str,
) -> str | None:
    """Submit a student assignment. Returns error string or None on success."""
    try:
        response = grpc_helper.assignment_stub.submitAssignment(
            _assignment_upload_chunks(assignment_file, filename, assignment_name),
            metadata=(("authorization", grpc_helper.access_token),),
        )
        if response.code == "200":
            return None
        return response.error
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return str(exc)


def get_submitted_assignments(course: str, assignment_name: str) -> tuple:
    """Download all submissions for an assignment as a ZIP. Returns (bytes, error)."""
    try:
        data = b""
        code = error = None
        for chunk in grpc_helper.assignment_stub.getSubmittedAssignment(
            Lms_pb2.GetSubmittedAssignmentsRequest(course=COURSE_ID, assignment_name=ASSIGNMENT_ID),
            metadata=(("authorization", grpc_helper.access_token),),
        ):
            data += chunk.data
            code = chunk.code
            error = chunk.error
        if not data:
            return None, "No Assignments"
        if code != "200":
            return None, "No Assignments"
        return data, None
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return None, exc.details()


# ---------------------------------------------------------------------------
# Queries RPCs
# ---------------------------------------------------------------------------

def create_query(course: str, query: str) -> str | None:
    """Create a student query. Returns error string or None on success."""
    try:
        response = grpc_helper.queries_stub.createQuery(
            Lms_pb2.CreateQueryRequest(course=COURSE_ID, query=query),
            metadata=(("authorization", grpc_helper.access_token),),
        )
        return response.error or None
    except grpc.RpcError as exc:
        return exc.details()


def get_queries(course: str, term: str) -> tuple:
    """Fetch all queries for a course. Returns (json_string, error)."""
    try:
        response = grpc_helper.queries_stub.getQueries(
            Lms_pb2.GetQueriesRequest(course=COURSE_ID, term=term),
            metadata=(("authorization", grpc_helper.access_token),),
        )
        return response.queries, None
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return None, exc.details()


def answer_query(query_id: str, answer: str) -> str | None:
    """Submit an instructor answer to a query. Returns error string or None."""
    try:
        response = grpc_helper.queries_stub.answerQuery(
            Lms_pb2.AnswerQueryRequest(qid=query_id, answer=answer),
            metadata=(("authorization", grpc_helper.access_token),),
        )
        return response.error or None
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.UNAVAILABLE:
            reconnect_to_leader()
        return exc.details()


# ---------------------------------------------------------------------------
# LLM Chat RPC
# ---------------------------------------------------------------------------

def _generate_chat_requests():
    """Generator that reads user input and yields AskLlmRequest messages."""
    print("Chat with NeuralNexus AI Tutor  |  Type 'quit' to exit")
    print("-" * 55)
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            print("Please enter a question.")
            continue
        if user_input.lower() == "quit":
            return
        yield Lms_pb2.AskLlmRequest(query=user_input)


def chat_with_tutor() -> str | None:
    """Start a bidirectional streaming chat with the Phi-3 AI tutor."""
    try:
        for response in grpc_helper.llm_stub.askLlm(
            _generate_chat_requests(),
            metadata=(("authorization", grpc_helper.access_token),),
        ):
            if response.error:
                print(f"[Error] {response.error}")
            else:
                print(f"Tutor: {response.reply}")
        return None
    except Exception as exc:
        return str(exc)


# Legacy aliases – kept so existing call-sites work without change
studentLogin = student_login
facultyLogin = faculty_login
getCourseContents = get_course_contents
getCourseMaterial = get_course_material
uploadMaterial = upload_material
submitAssignment = submit_assignment
getAssignments = get_submitted_assignments
chat_with_phi = chat_with_tutor
change_server = reconnect_to_leader
