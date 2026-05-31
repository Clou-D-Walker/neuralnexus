# System Design — NeuralNexus

## Design Goals

| Goal | Mechanism |
|---|---|
| **Fault tolerance** | Raft consensus — system continues while a majority of nodes are alive |
| **Strong consistency** | All writes go through the Raft leader and are applied only after majority ACK |
| **Intelligent tutoring** | Local Phi-3 inference — no external API dependency |
| **Secure sessions** | AES-256-CBC tokens with 2-hour TTL; SHA-256 password hashing |
| **Extensibility** | Modular service / handler / consensus layers; Raft dispatch tables |

---

## Component Responsibilities

### `services/` — Transport Boundary

Each servicer class in `services/` is the thinnest possible gRPC adapter:

1. Validates access using a role decorator (`@student_access_token_required`, etc.).
2. Extracts fields from the protobuf request.
3. For **write** operations: logs to Raft via `node.leader_append_log(op, args)`, then executes locally on the leader.
4. For **read** operations: queries the local SQLite directly.
5. Returns a protobuf response.

### `handlers/` — Business Logic

Handlers own:
- DB interactions (via `database/db_methods.py`).
- Filesystem I/O (`Resources/<course_id>/<filename>`).
- Raft **dispatch tables** (`assignments_map`, `materials_map`, `query_map`) — these are called during `apply()` on both the leader and all followers.

### `consensus/raft_node.py` — Consensus Engine

`Node` implements the full Raft state machine:

| Method | Role |
|---|---|
| `candidate_request_vote()` | Transitions to Candidate, increments term, solicits votes |
| `leader_append_log(op, args)` | Appends to log, replicates, returns commit index |
| `leader_append_entries()` | Parallel AppendEntries to all followers; returns majority ACK |
| `follower_append_entries(msg)` | Validates and appends log entries, applies commits |
| `follower_request_vote(req)` | Grants vote if candidate qualifies |

`Timer` drives two periodic jobs via APScheduler:

| Job | Interval | Action |
|---|---|---|
| Heartbeat | 100 ms | If Leader → send empty AppendEntries |
| Leader timeout | 200–400 ms (seeded by node UUID) | If no heartbeat received → start election |

### `security/` — Auth & Access Control

- **`settings.py`** — Pydantic-settings reads `AES_SECRET` and `NODE_ID` from `.env`.
- **`token_manager.py`** — `AESCipher` wraps PyCryptodome AES-256-CBC. Token format: `{user_id}|{role}|{YYYYMMDDHHmmss}`.
- **`access_control.py`** — Three gRPC decorators that read the `"authorization"` metadata key, decrypt and validate the token, then inject `kwargs["userid"]`.

---

## Write Path (detailed)

```
Client  ──gRPC──►  Service (e.g. MaterialsService.courseMaterialUpload)
                       │
                       ▼ @faculty_access_token_required
                   Decrypt token → validate role + expiry
                       │
                       ▼
                   node.leader_append_log("materials.material_upload", args)
                       │
                       ├─► INSERT INTO raft_logs (idx, term, op, args)
                       │
                       ├─► leader_append_entries()
                       │     ├─► AppendEntries → Follower 1  (parallel)
                       │     └─► AppendEntries → Follower 2  (parallel)
                       │               ▼
                       │        majority ACKs → return True
                       │
                       ├─► commit_index advances
                       │
                       └─► upload_material(conn, …)  ← actual DB + disk write on leader
                               │
                               ▼
                           Return gRPC success response to client
```

Followers apply the same operation asynchronously via `apply_committed_entries()` when the leader's `leader_commit_idx` advances in the next heartbeat.

---

## Read Path

Reads bypass Raft entirely — they query the local SQLite directly. Because all writes are eventually applied on every node, reads are eventually consistent (stale reads are possible on followers). For the current use case (course materials, queries) this is acceptable.

---

## File Storage Layout

```
server/
└── Resources/
    └── <course_id>/
        ├── <material_filename>          # uploaded by instructor
        └── <assignment_id>/
            └── <student_id>-<filename>  # student submissions
```

---

## Known Limitations & Future Improvements

| Issue | Notes |
|---|---|
| No TLS | All gRPC channels are insecure. Add TLS certificates for production. |
| Hardcoded IDs in client | `COURSE_ID` and `ASSIGNMENT_ID` are constants in `rpc_client.py`. Replace with dynamic course selection. |
| Single database file | SQLite is fine for a lab environment; replace with PostgreSQL for production scale. |
| Leader write amplification | The leader writes to the DB both through the Raft log (for followers) and directly. A crash between the two could cause a one-entry divergence. |
| No log compaction | The `raft_logs` table grows unboundedly. Implement snapshots for long-running deployments. |
| LLM context window | `context_limit=1` retains only the last exchange. Increase for richer conversations. |
