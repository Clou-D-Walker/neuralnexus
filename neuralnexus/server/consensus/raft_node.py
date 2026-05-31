"""
consensus/raft_node.py
----------------------
Raft consensus implementation for NeuralNexus distributed nodes.

Architecture
~~~~~~~~~~~~
- ``Node``  – Core Raft state machine (Follower / Candidate / Leader).
- ``Timer`` – APScheduler-based heartbeat and election-timeout scheduler.

Persistence
~~~~~~~~~~~
Raft state (term, log index, voted_for) is stored in the ``state_info``
SQLite table.  Log entries are stored in ``raft_logs``.

Node discovery is read from the ``node_discovery`` table at startup.

Module-level singletons
~~~~~~~~~~~~~~~~~~~~~~~
``node``  – The ``Node`` instance for this process.
``timer`` – The ``Timer`` instance driving heartbeat / election logic.
"""

import json
import concurrent.futures
import threading
import os
import sqlite3
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List

DB_PATH: str = os.environ.get("DB_PATH", "lms.db")

import grpc
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from proto import Lms_pb2, Lms_pb2_grpc
from database.db_methods import gen_uuid
from core.utils import get_timestamp
from security.settings import settings
from handlers.assignments_handler import assignments_map
from handlers.queries_handler import query_map
from handlers.materials_handler import materials_map

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Millisecond-precision scheduler helpers
# ---------------------------------------------------------------------------

class MillisecondIntervalTrigger(IntervalTrigger):
    """APScheduler trigger with millisecond resolution."""

    def __init__(self, milliseconds: int = 1000, **kwargs) -> None:
        self.milliseconds = milliseconds
        super().__init__(seconds=timedelta(milliseconds=milliseconds).total_seconds(), **kwargs)

    def get_next_fire_time(self, previous_fire_time, now):
        if previous_fire_time:
            next_fire = previous_fire_time + timedelta(milliseconds=self.milliseconds)
            if next_fire <= now:
                next_fire = now + timedelta(milliseconds=self.milliseconds)
            return next_fire
        return now + timedelta(milliseconds=self.milliseconds)


class MillisecondScheduler(BackgroundScheduler):
    """BackgroundScheduler subclass that adds millisecond-interval job support."""

    def add_millisecond_job(self, func, milliseconds: int, **kwargs):
        trigger = MillisecondIntervalTrigger(milliseconds=milliseconds)
        return self.add_job(func, trigger, **kwargs)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _get_random_leader_timeout(node_id: str) -> int:
    """Return a deterministic random election timeout (200-400 ms) seeded by node UUID."""
    random.seed(node_id)
    return random.randint(200, 400)


def _init_index_map(nodes: List[dict], value: int) -> dict:
    return {n["id"]: value for n in nodes}


def _discover_nodes() -> Tuple[Optional[dict], List[dict]]:
    """
    Read the cluster topology from the ``node_discovery`` SQLite table.

    Returns (cur_node_info, peer_node_list).
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, host, port FROM node_discovery")
        rows = cur.fetchall()

    cur_node = None
    peers: List[dict] = []
    for row in rows:
        info = {"id": row[0], "host": row[1], "port": row[2]}
        if info["id"] == settings.NODE_ID:
            cur_node = info
        else:
            peers.append(info)
    return cur_node, peers


# ---------------------------------------------------------------------------
# Raft log application
# ---------------------------------------------------------------------------

def apply(operation: str, args: dict) -> None:
    """
    Apply a committed Raft log entry to the local state machine.

    Dispatches to the appropriate handler map based on the operation prefix
    (e.g. "assignments.submit_assignment" → assignments_map["submit_assignment"]).
    """
    with sqlite3.connect(DB_PATH) as conn:
        module, func = operation.split(".")
        # Replace the placeholder "conn" value with a live connection
        hydrated_args = {k: (conn if k == "conn" else v) for k, v in args.items()}
        if module == "assignments":
            assignments_map[func](**hydrated_args)
        elif module == "materials":
            materials_map[func](**hydrated_args)
        elif module == "queries":
            query_map[func](**hydrated_args)


# ---------------------------------------------------------------------------
# Raft Node
# ---------------------------------------------------------------------------

class Node:
    """
    Core Raft state machine.

    States
    ------
    "F"  Follower  (default)
    "C"  Candidate (during election)
    "L"  Leader    (after winning election)
    """

    FOLLOWER  = "F"
    CANDIDATE = "C"
    LEADER    = "L"

    def __init__(self) -> None:
        self.cur_node, self.nodes = _discover_nodes()
        self.committed_index: int = 0
        self.last_applied: int = 0
        self.state: str = self.FOLLOWER
        self.leader_node: Optional[str] = None
        self.next_index: dict = _init_index_map(self.nodes, 1)
        self.match_index: dict = _init_index_map(self.nodes, 0)
        self.heartbeat_tracker: int = 0
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # LEADER: election
    # ------------------------------------------------------------------

    def candidate_request_vote(self) -> bool:
        """
        Initiate a leader election.

        Transitions to Candidate, increments term, votes for self, and
        sends RequestVote RPCs to all peers in parallel.  Becomes Leader on
        majority, reverts to Follower otherwise.
        """
        with sqlite3.connect(DB_PATH) as conn:
            state = self.get_state_info(conn)
            self.set_state(self.CANDIDATE)
            self.set_term(state["term"] + 1, conn)
            state = self.get_state_info(conn)
            votes_received = 1  # vote for self
            self.set_voted_for(self.cur_node["id"], conn)

            cur = conn.cursor()
            cur.execute("SELECT idx, term FROM raft_logs ORDER BY idx DESC LIMIT 1")
            res = cur.fetchone()
            last_index, last_term = (res[0], res[1]) if res else (0, 0)

        vote_args = {
            "term": state["term"],
            "node_id": self.cur_node["id"],
            "last_log_idx": last_index,
            "last_log_term": last_term,
        }
        majority = (len(self.nodes) + 1) // 2

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.nodes) + 1) as executor:
            futures = {
                executor.submit(self._send_request_vote, peer, vote_args): peer
                for peer in self.nodes
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    granted, peer_term = future.result()
                    if granted:
                        votes_received += 1
                    with sqlite3.connect(DB_PATH) as conn:
                        if peer_term > state["term"]:
                            self.set_term(peer_term, conn)
                            self.set_state(self.FOLLOWER)
                            timer.reset_leader_timeout()
                            return False
                        if votes_received > majority:
                            self.set_state(self.LEADER)
                            self.leader_node = self.cur_node["id"]
                            logger.info("Leader elected – I am the LEADER (%s)", self.cur_node["id"])
                            print(f"[Raft] Leader elected! Node: {self.cur_node['id']}")
                            self.next_index = _init_index_map(self.nodes, last_index + 1)
                            self.match_index = _init_index_map(self.nodes, 0)
                            self.leader_append_entries()
                            return True
                except Exception:
                    pass

        timer.reset_leader_timeout()
        return False

    def _send_request_vote(self, peer: dict, vote_request: dict) -> Tuple[bool, int]:
        """Send a RequestVote RPC to *peer*. Returns (vote_granted, peer_term)."""
        try:
            with grpc.insecure_channel(f"{peer['host']}:{peer['port']}") as channel:
                stub = Lms_pb2_grpc.RaftStub(channel)
                response = stub.requestVote(
                    Lms_pb2.RequestVoteRequest(**vote_request), timeout=1
                )
                return response.vote_granted, response.term
        except Exception:
            return False, vote_request["term"]

    # ------------------------------------------------------------------
    # LEADER: log replication
    # ------------------------------------------------------------------

    def leader_append_log(self, operation: str, args: dict) -> Optional[int]:
        """
        Append a new entry to the Raft log and replicate it to followers.

        Returns the committed log index on success, or None on error.
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                state = self.get_state_info(conn)
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO raft_logs(id, operation, args, term, idx, created_at) "
                    "VALUES(?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (gen_uuid(), operation, json.dumps(args), state["term"], state["idx"] + 1),
                )
                conn.commit()
                new_idx = self._increment_idx(state["idx"], conn)

            replicated = self.leader_append_entries()
            if replicated:
                self._set_committed_index(new_idx)
                self._set_last_applied(new_idx)
            return new_idx
        except Exception as exc:
            logger.error("leader_append_log error: %s", exc)
            return None

    def leader_append_entries(self) -> bool:
        """
        Send AppendEntries RPCs to all followers in parallel.

        Returns True once a majority acknowledges the latest log entries.
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                state = self.get_state_info(conn)

            enriched_nodes = []
            for peer in self.nodes:
                peer_copy = dict(peer)
                peer_copy["term"] = state["term"]
                peer_copy["committed_index"] = self.get_committed_index()
                peer_copy["leader_node"] = self.leader_node
                peer_copy["idx"] = self._get_next_index(peer["id"])
                enriched_nodes.append(peer_copy)

            acks = 1
            committed = False
            majority = (len(self.nodes) + 1) // 2

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._append_entries_to_peer, peer): peer
                    for peer in enriched_nodes
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        success, _ = future.result()
                        if success:
                            acks += 1
                        if acks > majority:
                            committed = True
                            break
                    except Exception as exc:
                        logger.debug("AppendEntries future error: %s", exc)
                executor.shutdown(cancel_futures=True)

            return committed
        except Exception as exc:
            logger.error("leader_append_entries error: %s", exc)
            return False

    def _append_entries_to_peer(self, peer: dict) -> Tuple[bool, Optional[int]]:
        """
        Send AppendEntries to a single follower peer.

        Handles log backtracking on consistency failures.
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                # Fetch the entry just before what the peer expects
                cur.execute(
                    "SELECT idx, term FROM raft_logs WHERE idx = ? - 1 ORDER BY idx",
                    (peer["idx"],),
                )
                prev = cur.fetchone()
                prev_idx = prev[0] if prev else 0
                prev_term = prev[1] if prev else 0

                cur.execute(
                    "SELECT idx, term, operation, args FROM raft_logs WHERE idx >= ? ORDER BY idx",
                    (peer["idx"],),
                )
                rows = cur.fetchall()

            entries = []
            last_idx = None
            for row in rows:
                entries.append({
                    "idx": row[0],
                    "term": row[1],
                    "operation": row[2],
                    "args": row[3],
                })
                last_idx = row[0]

            payload = {
                "term": peer["term"],
                "leader_id": peer["leader_node"],
                "leader_commit_idx": peer["committed_index"],
                "prev_log_idx": prev_idx,
                "prev_log_term": prev_term,
                "entries": json.dumps({"entries": entries}),
            }

            try:
                with grpc.insecure_channel(f"{peer['host']}:{peer['port']}") as channel:
                    stub = Lms_pb2_grpc.RaftStub(channel)
                    response = stub.appendEntries(
                        Lms_pb2.AppendEntriesRequest(**payload), timeout=1
                    )
                success, resp_term = response.success, response.term
            except Exception:
                return False, None

            if success:
                if last_idx:
                    self._set_next_index(peer["id"], last_idx + 1)
                    self._set_match_index(peer["id"], last_idx)
                return True, last_idx

            # Handle failure
            if resp_term == peer["term"]:
                # Log inconsistency – back off peer's next_index
                self._set_next_index(peer["id"], max(1, prev_idx))
                return True, None
            if resp_term > peer["term"]:
                with sqlite3.connect(DB_PATH) as conn:
                    self.set_term(resp_term, conn)
                self.set_state(self.FOLLOWER)
                return True, None
            return False, None

        except Exception as exc:
            logger.debug("_append_entries_to_peer error: %s", exc)
            return False, None

    # ------------------------------------------------------------------
    # FOLLOWER: AppendEntries handler
    # ------------------------------------------------------------------

    def follower_append_entries(self, log_message: dict) -> Tuple[bool, int]:
        """
        Process an AppendEntries RPC as a follower.

        Validates log consistency, appends new entries, and applies
        committed entries when the leader's commit index advances.
        """
        try:
            self._increment_heartbeat()
            entries = json.loads(log_message["entries"])["entries"]

            with sqlite3.connect(DB_PATH) as conn:
                state = self.get_state_info(conn)

                if log_message["term"] > state["term"]:
                    self.set_term(log_message["term"], conn)
                    self.state = self.FOLLOWER
                    state = self.get_state_info(conn)
                    timer.reset_leader_timeout()
                elif log_message["term"] < state["term"]:
                    return False, state["term"]

                # Heartbeat with no entries
                if not entries and log_message["prev_log_idx"] == 0:
                    return True, log_message["term"]

                cur = conn.cursor()
                if log_message["prev_log_idx"] != 0:
                    cur.execute(
                        "SELECT idx, term FROM raft_logs WHERE idx = ? AND term = ?",
                        (log_message["prev_log_idx"], log_message["prev_log_term"]),
                    )
                    if not cur.fetchone():
                        return False, state["term"]

                idx = state["idx"]
                for entry in entries:
                    cur.execute(
                        "INSERT INTO raft_logs (idx, term, operation, args) "
                        "VALUES (?, ?, ?, ?) ON CONFLICT(idx, term) DO NOTHING",
                        (entry["idx"], entry["term"], entry["operation"], entry["args"]),
                    )
                    idx = entry["idx"]

                if idx > state["idx"]:
                    self._set_idx(idx, conn)
                conn.commit()

                commit_idx = self.get_committed_index()
                if log_message["leader_commit_idx"] > commit_idx:
                    commit_idx = min(log_message["leader_commit_idx"], idx)
                    self._apply_committed_entries(commit_idx, conn)

            return True, state["term"]
        except Exception as exc:
            logger.debug("follower_append_entries error: %s", exc)
            return False, log_message["term"]

    def _apply_committed_entries(self, commit_idx: int, conn: sqlite3.Connection) -> None:
        """Apply all uncommitted log entries up to *commit_idx*."""
        cur = conn.cursor()
        cur.execute(
            "SELECT idx, term, operation, args FROM raft_logs "
            "WHERE idx <= ? AND idx > ? ORDER BY idx",
            (commit_idx, self.get_last_applied()),
        )
        for row in cur.fetchall():
            apply(row[2], json.loads(row[3]))
            self._set_last_applied(row[0])
        self._set_committed_index(commit_idx)
        conn.commit()
        cur.close()

    # ------------------------------------------------------------------
    # FOLLOWER: RequestVote handler
    # ------------------------------------------------------------------

    def follower_request_vote(self, request: dict):
        """
        Process a RequestVote RPC as a follower.

        Grants the vote if the candidate's term is current, no vote has
        been cast in this term, and the candidate's log is at least as
        up-to-date.
        """
        try:
            with sqlite3.connect(DB_PATH) as conn:
                state = self.get_state_info(conn)

                if request["term"] < state["term"]:
                    return Lms_pb2.RequestVoteResponse(vote_granted=False, term=state["term"])

                if request["term"] > state["term"]:
                    self.set_term(request["term"], conn)
                    self.set_state(self.FOLLOWER)

                if state["voted_for"] and state["voted_for"] != request["candidate_id"]:
                    return Lms_pb2.RequestVoteResponse(vote_granted=False, term=state["term"])

                cur = conn.cursor()
                cur.execute("SELECT idx, term FROM raft_logs ORDER BY idx DESC LIMIT 1")
                res = cur.fetchone()
                last_index, last_term = (res[0], res[1]) if res else (0, 0)

                candidate_log_stale = (
                    request["last_log_term"] < last_term
                    or (
                        request["last_log_term"] == last_term
                        and request["last_log_idx"] < last_index
                    )
                )
                if candidate_log_stale:
                    return Lms_pb2.RequestVoteResponse(vote_granted=False, term=state["term"])

                self.set_voted_for(request["candidate_id"], conn)
                logger.info(
                    "Granted vote to candidate %s for term %s",
                    request["candidate_id"],
                    request["term"],
                )
                timer.reset_leader_timeout()
                return Lms_pb2.RequestVoteResponse(vote_granted=True, term=request["term"])

        except Exception as exc:
            logger.error("follower_request_vote error: %s", exc)
            return Lms_pb2.RequestVoteResponse(vote_granted=False, term=request["term"])

    # ------------------------------------------------------------------
    # State management helpers (SQLite-backed)
    # ------------------------------------------------------------------

    def get_state_info(self, conn: sqlite3.Connection) -> dict:
        """Return a dict with keys: term, idx, voted_for, state."""
        cur = conn.cursor()
        cur.execute("SELECT term, idx, voted_for FROM state_info LIMIT 1")
        res = cur.fetchone()
        cur.close()
        return {"term": res[0], "idx": res[1], "voted_for": res[2], "state": self.state}

    def set_term(self, term: int, conn: sqlite3.Connection) -> int:
        cur = conn.cursor()
        cur.execute("UPDATE state_info SET term = ?, voted_for = NULL", (term,))
        conn.commit()
        cur.close()
        return term

    def set_voted_for(self, voted_for: str, conn: sqlite3.Connection) -> str:
        cur = conn.cursor()
        cur.execute("UPDATE state_info SET voted_for = ?", (voted_for,))
        conn.commit()
        cur.close()
        return voted_for

    def set_state(self, state: str) -> str:
        with self._lock:
            self.state = state
        return state

    def _increment_idx(self, idx: int, conn: sqlite3.Connection) -> int:
        cur = conn.cursor()
        cur.execute("UPDATE state_info SET idx = idx + 1")
        conn.commit()
        cur.close()
        return idx + 1

    def _set_idx(self, idx: int, conn: sqlite3.Connection) -> int:
        cur = conn.cursor()
        cur.execute("UPDATE state_info SET idx = ?", (idx,))
        cur.close()
        return idx

    # ------------------------------------------------------------------
    # In-memory index tracking (Leader only)
    # ------------------------------------------------------------------

    def _set_next_index(self, node_id: str, idx: int) -> None:
        self.next_index[node_id] = idx

    def _set_match_index(self, node_id: str, idx: int) -> None:
        self.match_index[node_id] = idx

    def _get_next_index(self, node_id: str) -> int:
        return self.next_index[node_id]

    def _get_match_index(self, node_id: str) -> int:
        return self.match_index[node_id]

    def _set_last_applied(self, idx: int) -> None:
        self.last_applied = idx

    def get_last_applied(self) -> int:
        return self.last_applied

    def _set_committed_index(self, idx: int) -> None:
        self.committed_index = idx

    def get_committed_index(self) -> int:
        return self.committed_index

    def _increment_heartbeat(self) -> None:
        self.heartbeat_tracker = (self.heartbeat_tracker + 1) % 100

    def get_heartbeat_tracker(self) -> int:
        return self.heartbeat_tracker

    def get_leader_info(self, node_id: str) -> Optional[dict]:
        """Return host/port info for a given node ID from node_discovery."""
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, host, port FROM node_discovery WHERE id = ?", (node_id,)
            )
            res = cur.fetchone()
            if res:
                return {"id": res[0], "host": res[1], "port": res[2]}
            return None


# ---------------------------------------------------------------------------
# Raft Timer
# ---------------------------------------------------------------------------

class Timer:
    """
    Drives the Raft timing logic:
    - Heartbeat job (100 ms): If this node is Leader, send heartbeat AppendEntries.
    - Leader-timeout job (200-400 ms): If not Leader and no heartbeat received, start election.
    """

    HEARTBEAT_INTERVAL_MS = 100

    def __init__(self, node_id: str) -> None:
        self._heartbeat_interval = self.HEARTBEAT_INTERVAL_MS
        self._leader_timeout = _get_random_leader_timeout(node_id)
        self._scheduler = MillisecondScheduler()
        self._hb_job = self._scheduler.add_millisecond_job(
            self._heartbeat_tick, milliseconds=self._heartbeat_interval, max_instances=10
        )
        self._lt_job = self._scheduler.add_millisecond_job(
            self._leader_timeout_tick, milliseconds=self._leader_timeout, max_instances=10
        )
        self._last_heartbeat_val = 0

    def _heartbeat_tick(self) -> None:
        """Triggered every heartbeat interval. Leaders send AppendEntries (keepalive)."""
        with sqlite3.connect(DB_PATH) as conn:
            state = node.get_state_info(conn)["state"]
        if state == Node.LEADER:
            node.leader_append_entries()

    def _leader_timeout_tick(self) -> None:
        """
        Triggered periodically.  If this node has not seen a heartbeat since
        the last check, it starts an election.
        """
        with sqlite3.connect(DB_PATH) as conn:
            state = node.get_state_info(conn)["state"]
        if state != Node.LEADER:
            current_hb = node.get_heartbeat_tracker()
            if self._last_heartbeat_val == current_hb:
                node.candidate_request_vote()
            else:
                self._last_heartbeat_val = current_hb

    def start(self) -> None:
        print(f"[Raft] Leader timeout: {self._leader_timeout} ms")
        self._scheduler.start()

    def stop(self) -> None:
        self._scheduler.shutdown()

    def pause(self) -> None:
        self._scheduler.pause()

    def resume(self) -> None:
        self._scheduler.resume()

    def reset_leader_timeout(self) -> None:
        """Remove and re-add the leader-timeout job to reset the countdown."""
        self._lt_job.remove()
        self._lt_job = self._scheduler.add_millisecond_job(
            self._leader_timeout_tick,
            milliseconds=self._leader_timeout,
            max_instances=5,
        )

    def reset_heartbeat(self) -> None:
        """Remove and re-add the heartbeat job."""
        self._hb_job.remove()
        self._hb_job = self._scheduler.add_millisecond_job(
            self._heartbeat_tick,
            milliseconds=self._heartbeat_interval,
            max_instances=5,
        )

    # Legacy method aliases
    reset_lt = reset_leader_timeout
    reset_ht = reset_heartbeat


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

node = Node()
timer = Timer(node.cur_node["id"])
