"""
services/llm_service.py
------------------------
gRPC servicer for the NeuralNexus AI tutoring endpoint.
"""

from proto import Lms_pb2, Lms_pb2_grpc
from handlers.llm_handler import create_chat_session
from security.access_control import any_access_token_required


class LlmService(Lms_pb2_grpc.LlmServicer):
    """Handles bidirectional streaming chat with the Phi-3 LLM."""

    @any_access_token_required
    def askLlm(self, request_iterator, context, **kwargs):
        chat_pipeline = create_chat_session()
        for request in request_iterator:
            reply = chat_pipeline.add_message(request.query)
            yield Lms_pb2.AskLlmResponse(reply=reply, code="200")
