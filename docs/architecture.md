# Architecture — NeuralNexus

## Overview

NeuralNexus is a distributed Learning Management System built on two orthogonal foundations:

1. **Raft consensus** — every write operation is logged, replicated to a majority of nodes, and only then applied. This ensures all nodes converge to the same state even in the presence of failures.
2. **Phi-3 LLM** — a locally-served quantised language model answers student questions in real time via a bidirectional gRPC stream. The model file must be placed at `neuralnexus/server/Model/Phi-3-Context-Obedient-RAG-Q4_K_M.gguf` (inside the server directory, not the repo root). Without it the server still starts normally — only the AI tutoring feature is disabled.

---

## System Components

```
┌────────────────────────────────────────────────────────────────┐
│                       NeuralNexus Client                        │
│                                                                  │
│  client_entry.py ──► leader discovery (getLeader RPC)          │
│        │                                                         │
│        ▼                                                         │
│  connect_to_leader() ──► grpc stubs (Auth/Materials/…/Raft)    │
│        │                                                         │
│        ▼                                                         │
│  ui_actions.py ──► menu_renderer.py (recursive CLI menus)       │
└────────────────────────┬─────────────────────────────────────── ┘
                         │  gRPC (insecure channels, port 5005x)
    ┌────────────────────┼────────────────────────────────┐
    ▼                    ▼                                 ▼
 Node A (leader)      Node B (follower)              Node C (follower)
┌───────────────┐   ┌───────────────┐              ┌───────────────┐
│ services/     │   │ services/     │              │ services/     │
│  auth         │   │  auth         │              │  auth         │
│  materials    │   │  materials    │              │  materials    │
│  assignments  │   │  assignments  │              │  assignments  │
│  queries      │   │  queries      │              │  queries      │
│  llm          │   │  llm          │              │  llm          │
│  raft  ◄──────┼───►  raft  ◄─────┼──────────────►  raft         │
│               │   │               │              │               │
│ consensus/    │   │ consensus/    │              │ consensus/    │
│  raft_node    │   │  raft_node    │              │  raft_node    │
│               │   │               │              │               │
│ database/     │   │ database/     │              │ database/     │
│  lms.db       │   │  lms.db       │              │  lms.db       │
└───────────────┘   └───────────────┘              └───────────────┘
```

---

## Module Layer Map

| Layer | Directory | Responsibility |
|---|---|---|
| Entry Point | `server_entry.py` | Bootstrap DB, register servicers, start Raft timer |
| Services | `services/` | gRPC servicer classes, access-control decorators applied here |
| Handlers | `handlers/` | Business logic, DB writes, filesystem I/O |
| Consensus | `consensus/` | Raft state machine (`Node`) + scheduler (`Timer`) |
| Database | `database/` | SQLite schema, all raw SQL queries |
| Security | `security/` | AES token management, role-based decorators, `.env` settings |
| Proto | `proto/` | `.proto` definition + generated `Lms_pb2` / `Lms_pb2_grpc` |
| Core | `core/` | Shared stdlib imports, utility functions |

---

## Raft Consensus Workflow

```mermaid
sequenceDiagram
    participant C as Client
    participant L as Leader Node
    participant F1 as Follower 1
    participant F2 as Follower 2

    C->>L: gRPC write request (e.g. submitAssignment)
    L->>L: leader_append_log(operation, args)
    L->>L: INSERT INTO raft_logs (idx, term, operation, args)
    par Parallel replication
        L->>F1: AppendEntries RPC
        L->>F2: AppendEntries RPC
    end
    F1-->>L: success=true
    F2-->>L: success=true
    Note over L: majority acknowledged (2/3 nodes)
    L->>L: commit_index advances
    L->>L: apply(operation, args) → DB write
    F1->>F1: apply committed entries
    F2->>F2: apply committed entries
    L-->>C: gRPC success response
```

**Key properties:**
- Writes only succeed when a majority of nodes (⌊N/2⌋ + 1) acknowledge.
- All writes are idempotent in the log (`ON CONFLICT … DO NOTHING`).
- The leader timer fires every 100 ms; followers time out at a seeded-random 200–400 ms.
- **Single-node mode:** With only Node 1 running, majority resolves to 1 (self-vote is sufficient). Node 1 elects itself leader and all operations succeed — useful for quick local testing but does not demonstrate fault-tolerance. Use all 3 nodes for a proper distributed demo.

---

## Leader Election

```mermaid
sequenceDiagram
    participant F as Follower (timeout)
    participant C as Candidate
    participant P1 as Peer 1
    participant P2 as Peer 2

    F->>C: becomes Candidate (term+1, votes for self)
    par Send RequestVote
        C->>P1: RequestVote(term, lastLogIdx, lastLogTerm)
        C->>P2: RequestVote(term, lastLogIdx, lastLogTerm)
    end
    P1-->>C: vote_granted=true
    Note over C: majority reached → become LEADER
    C->>P1: AppendEntries (empty, announces leadership)
    C->>P2: AppendEntries (empty, announces leadership)
```

---

## LLM Tutoring Workflow

> **Model location:** `neuralnexus/server/Model/Phi-3-Context-Obedient-RAG-Q4_K_M.gguf`
> This path is relative to `neuralnexus/server/` (the server's working directory) — **not** the repo root.
> The model is loaded lazily on first use. If the file is absent the service starts but returns an error on LLM calls.
> See [development-guide.md](development-guide.md#enabling-ai--llm-features) for install instructions.

```mermaid
sequenceDiagram
    participant S as Student CLI
    participant G as LlmService (gRPC)
    participant P as ModelPipeline (Phi-3)

    S->>G: stream AskLlmRequest(query)
    G->>P: create_chat_session()
    loop for each message
        S->>G: AskLlmRequest(query)
        G->>P: add_message(query)
        P->>P: format_chat_template(context + query)
        P->>P: model(prompt, max_tokens=80)
        P-->>G: reply_text
        G-->>S: AskLlmResponse(reply=reply_text)
    end
```

---

## Authentication Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as AuthService
    participant H as auth_handler
    participant T as token_manager

    C->>C: sha256(password) → hashed_pwd
    C->>A: studentLogin(username, hashed_pwd)
    A->>H: login(username, hashed_pwd, "Student")
    H->>H: validate_user(conn, ...) → user_id
    H->>T: encrypt("{user_id}|Student|{expiry}")
    T-->>H: AES-256-CBC token (base64url)
    H-->>A: token
    A-->>C: LoginResponse(token=token, code="200")

    Note over C: All subsequent RPCs include:
    Note over C: metadata: ("authorization", token)
```

---

## Database Schema

```
roles ←──── users ────┬──── courses ────┬──── materials
                      │                  │
                      ▼                  ├──── assignments ──── assignment_submissions
                course_enrolled          │
                                         └──── queries

node_discovery    raft_logs    state_info
```

| Table | Primary Key | Notes |
|---|---|---|
| `roles` | id (uuid) | Student / Instructor |
| `users` | id (uuid) | FK → roles |
| `courses` | id (uuid) | FK → users (instructor) |
| `course_enrolled` | (course_id, user_id) | Many-to-many |
| `assignments` | id (uuid) | FK → courses |
| `assignment_submissions` | (assignment_id, user_id) | INSERT OR REPLACE |
| `materials` | id (uuid) | FK → courses |
| `queries` | id (uuid) | FK → courses, users |
| `node_discovery` | id (uuid) | Cluster topology |
| `raft_logs` | id (uuid) | UNIQUE (idx, term) |
| `state_info` | — | Single row: term, idx, voted_for |
