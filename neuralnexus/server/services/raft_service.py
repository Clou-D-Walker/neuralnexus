"""
services/raft_service.py
------------------------
gRPC servicer for the NeuralNexus Raft consensus protocol endpoints.
"""

from proto import Lms_pb2, Lms_pb2_grpc
from consensus.raft_node import node


class RaftService(Lms_pb2_grpc.RaftServicer):
    """Exposes Raft RPCs: appendEntries, requestVote, getLeader."""

    def appendEntries(self, request, context):
        try:
            log_message = {
                "term": request.term,
                "leader_id": request.leader_id,
                "prev_log_idx": request.prev_log_idx,
                "prev_log_term": request.prev_log_term,
                "entries": request.entries,
                "leader_commit_idx": request.leader_commit_idx,
            }
            success, term = node.follower_append_entries(log_message)
            return Lms_pb2.AppendEntriesResponse(term=term, success=success)
        except Exception as exc:
            print(f"[RaftService] appendEntries error: {exc}")
            return Lms_pb2.AppendEntriesResponse(success=False, term=request.term)

    def requestVote(self, request, context):
        try:
            vote_request = {
                "term": request.term,
                "candidate_id": request.node_id,
                "last_log_idx": request.last_log_idx,
                "last_log_term": request.last_log_term,
            }
            return node.follower_request_vote(vote_request)
        except Exception as exc:
            print(f"[RaftService] requestVote error: {exc}")
            return Lms_pb2.RequestVoteResponse(term=request.term, vote_granted=False)

    def getLeader(self, request, context):
        try:
            leader_id = node.leader_node or ""
            return Lms_pb2.GetLeaderResponse(node_id=leader_id)
        except Exception as exc:
            print(f"[RaftService] getLeader error: {exc}")
            return Lms_pb2.GetLeaderResponse(node_id="")
