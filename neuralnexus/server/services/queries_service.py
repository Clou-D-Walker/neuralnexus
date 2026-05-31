"""
services/queries_service.py
----------------------------
gRPC servicer for NeuralNexus student Q&A query management.
"""

import json
import os
import sqlite3

DB_PATH: str = os.environ.get("DB_PATH", "lms.db")

from proto import Lms_pb2, Lms_pb2_grpc
from consensus.raft_node import node
from handlers.queries_handler import create_query, get_queries, answer_query
from security.access_control import (
    student_access_token_required,
    faculty_access_token_required,
    any_access_token_required,
)


class QueryService(Lms_pb2_grpc.QueriesServicer):
    """Handles course Q&A query RPCs."""

    @student_access_token_required
    def createQuery(self, request, context, **kwargs):
        try:
            course = request.course
            query_text = request.query
            with sqlite3.connect(DB_PATH) as conn:
                raft_args = {
                    "conn": "conn",
                    "course": course,
                    "query": query_text,
                    "user_id": kwargs["userid"],
                }
                replicated = node.leader_append_log("queries.create_query", raft_args)
                if not replicated:
                    return Lms_pb2.CreateQueryResponse(
                        error="Majority of nodes are down", code="500"
                    )
                error = create_query(conn, course, query_text, kwargs["userid"])
            if error:
                return Lms_pb2.CreateQueryResponse(error=str(error), code="400")
            return Lms_pb2.CreateQueryResponse(code="200")
        except Exception as exc:
            print(exc)
            return Lms_pb2.CreateQueryResponse(error=str(exc), code="400")

    @any_access_token_required
    def getQueries(self, request, context, **kwargs):
        try:
            course = request.course
            with sqlite3.connect(DB_PATH) as conn:
                queries, error = get_queries(conn, course)
            if error:
                return Lms_pb2.GetQueriesResponse(error=str(error), code="400")
            return Lms_pb2.GetQueriesResponse(
                code="200", queries=json.dumps({"q": queries})
            )
        except Exception as exc:
            print(exc)
            return Lms_pb2.GetQueriesResponse(error=str(exc), code="400")

    @faculty_access_token_required
    def answerQuery(self, request, context, **kwargs):
        try:
            answer = request.answer
            query_id = request.qid
            with sqlite3.connect(DB_PATH) as conn:
                raft_args = {
                    "conn": "conn",
                    "queryid": query_id,
                    "answer": answer,
                    "user_id": kwargs["userid"],
                }
                replicated = node.leader_append_log("queries.answer_query", raft_args)
                if not replicated:
                    return Lms_pb2.AnswerQueryResponse(
                        error="Majority of nodes are down", code="500"
                    )
                error = answer_query(conn, query_id, answer, kwargs["userid"])
            if error:
                return Lms_pb2.AnswerQueryResponse(error=str(error), code="400")
            return Lms_pb2.AnswerQueryResponse(code="200")
        except Exception as exc:
            print(exc)
            return Lms_pb2.AnswerQueryResponse(error=str(exc), code="400")
