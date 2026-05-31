# NeuralNexus

**Distributed AI Learning Platform**

NeuralNexus is a fault-tolerant, distributed Learning Management System that combines **Raft-based consensus** for strong data consistency across nodes with a **Phi-3 LLM** for intelligent, context-aware AI tutoring.

---

## Key Features

| Feature | Implementation |
|---|---|
| Distributed consistency | Raft consensus (leader election + log replication) |
| AI tutoring | Phi-3 GGUF model via `llama-cpp-python` |
| Communication | gRPC (insecure channel, protobuf) |
| Authentication | AES-256-CBC encrypted session tokens |
| Password hashing | SHA-256 (client-side) |
| Storage | SQLite with Raft-replicated write log |

---

## Project Structure

```
neuralnexus/
├── server/                     # gRPC server (one instance per cluster node)
│   ├── server_entry.py         # Entry point – starts server + Raft timer
│   ├── seed_db.py              # One-time DB seeder (users, course, nodes)
│   ├── lms.db                  # Node 1 database (pre-seeded)
│   ├── .env                    # Node 1 config  (NODE_ID=ee1f954b…, AES_SECRET)
│   ├── node2/                  # Node 2 isolated data directory
│   │   ├── lms.db              # Node 2 database (copy of seeded DB)
│   │   └── .env                # Node 2 config  (NODE_ID=de3b3357…)
│   ├── node3/                  # Node 3 isolated data directory
│   │   ├── lms.db              # Node 3 database (copy of seeded DB)
│   │   └── .env                # Node 3 config  (NODE_ID=becedead…)
│   ├── services/               # gRPC servicer implementations
│   │   ├── auth_service.py
│   │   ├── materials_service.py
│   │   ├── assignments_service.py
│   │   ├── queries_service.py
│   │   ├── llm_service.py
│   │   └── raft_service.py
│   ├── handlers/               # Business logic (DB + filesystem operations)
│   │   ├── auth_handler.py
│   │   ├── materials_handler.py
│   │   ├── assignments_handler.py
│   │   ├── queries_handler.py
│   │   └── llm_handler.py
│   ├── consensus/              # Raft state machine + timer
│   │   └── raft_node.py
│   ├── database/               # SQLite schema and query functions
│   │   ├── schema.py
│   │   └── db_methods.py
│   ├── security/               # Auth, encryption, access-control decorators
│   │   ├── settings.py
│   │   ├── token_manager.py
│   │   └── access_control.py
│   ├── proto/                  # Protobuf definitions and generated code
│   │   └── Lms.proto
│   ├── core/                   # Shared imports and utility functions
│   │   ├── imports.py
│   │   └── utils.py
│   └── requirements.txt
└── client/                     # CLI client application
    ├── client_entry.py         # Entry point
    ├── rpc_client.py           # All gRPC transport calls
    ├── ui_actions.py           # Menu action handlers
    ├── menu_renderer.py        # Generic recursive menu renderer
    ├── session_manager.py      # GrpcHelper singleton (stub registry)
    ├── Lms.proto               # Proto definition (copy)
    └── node_discovery.json     # Bootstrap node list

docs/
├── architecture.md
├── system-design.md
├── api-overview.md
└── development-guide.md

start_node1.bat             # Launch Node 1 (port 50052)
start_node2.bat             # Launch Node 2 (port 50053)
start_node3.bat             # Launch Node 3 (port 50054)
start_client.bat            # Launch CLI client
```

---

## Quick Start

> **Interface:** NeuralNexus is a **terminal/CLI application**. There is no web or desktop frontend — all interaction happens through the command-line menu driven by `client_entry.py`.

### Prerequisites

- Python 3.9+ with a virtual environment at `env/` (Python 3.14 tested)
- Dependencies installed — run once from the repo root:
  ```cmd
  env\Scripts\activate
  pip install -r neuralnexus\server\requirements.txt
  ```
- *(Optional)* Phi-3 GGUF model for AI tutoring. The server starts and functions fully without it; only the LLM tutoring feature is disabled. When needed, place the model at:
  ```
  neuralnexus/server/Model/Phi-3-Context-Obedient-RAG-Q4_K_M.gguf
  ```
  The `Model/` folder lives inside `neuralnexus/server/` — **not** at the repo root. See [docs/development-guide.md](docs/development-guide.md#enabling-ai--llm-features) for full install steps.

### One-time setup (already done if you cloned this repo with the pre-seeded DB)

```cmd
REM Generate gRPC stubs (only needed after proto changes)
cd neuralnexus\server && call generate_proto_code.bat && cd ..\..
cd neuralnexus\client && call gen_proto_code.bat && cd ..\..

REM Seed the database (already done — skip if lms.db is present)
cd neuralnexus\server && python seed_db.py && cd ..\..
```

> **Fresh clone?** The `.env` files and `lms.db` are not committed. See [docs/development-guide.md](docs/development-guide.md#node-configuration) for the step-by-step guide on generating UUIDs, creating `.env` files from the `.env.example` templates, and seeding the database.

### Running the 3-node cluster (Windows)

**Quickest way — one double-click:**

```cmd
start_cluster.bat
```

This opens Node 1, 2, and 3 each in their own CMD window (1 second apart), then run `start_client.bat` in a new terminal after ~2 seconds.

**Or launch each window manually:**

| Terminal | Command | What it does |
|---|---|---|
| 1 | `start_node1.bat` | Node 1 — port 50052, leader-eligible |
| 2 | `start_node2.bat` | Node 2 — port 50053, leader-eligible |
| 3 | `start_node3.bat` | Node 3 — port 50054, leader-eligible |
| 4 | `start_client.bat` | CLI client — auto-discovers the leader |

Wait ~2 seconds after starting the server nodes before launching the client. One node will print `[Raft] Leader elected!` — that node is the current leader.

**Quick testing (single node):** `start_node1.bat` + `start_client.bat` is enough. Node 1 elects itself leader (majority = 1) and all features work. Does not demonstrate distributed consensus — use all 3 for demos.

#### Demo credentials

| Role | Username | Password |
|---|---|---|
| Instructor | `santosh` | `admin123` |
| Student | `surya` | `surya123` |
| Student | `abhi` | `abhi123` |

Course: **Graph Neural Networks** (`GNN01`) · Assignment: **Assignment 1** (due 2026-12-31)

### Manual launch (without batch scripts)

```cmd
REM Terminal 1 — Node 1
cd neuralnexus\server
set NODE_PORT=50052 && set DB_PATH=lms.db && set ENV_FILE=.env
env\Scripts\activate && python server_entry.py

REM Terminal 2 — Node 2
cd neuralnexus\server
set NODE_PORT=50053 && set DB_PATH=node2\lms.db && set ENV_FILE=node2\.env
env\Scripts\activate && python server_entry.py

REM Terminal 3 — Node 3
cd neuralnexus\server
set NODE_PORT=50054 && set DB_PATH=node3\lms.db && set ENV_FILE=node3\.env
env\Scripts\activate && python server_entry.py

REM Terminal 4 — Client
cd neuralnexus\client
env\Scripts\activate && python client_entry.py
```

---

## Technologies

| Technology | Version | Role |
|---|---|---|
| Python | 3.9+ | Core language |
| gRPC / grpcio | 1.66+ | RPC framework |
| Protocol Buffers | 5.x | Message serialization |
| SQLite | stdlib | Per-node persistent storage |
| Raft (custom) | — | Distributed consensus |
| APScheduler | 3.10.4 | Raft heartbeat / election timer |
| llama-cpp-python | 0.2.77 | Local LLM inference |
| Phi-3 GGUF | Q4_K_M | AI tutoring model |
| pycryptodome | 3.20.0 | AES-256-CBC session tokens |
| pydantic-settings | 2.x | Configuration management |

---

## Architecture Overview

See [docs/architecture.md](docs/architecture.md) for detailed diagrams and explanations.

```
┌──────────────────────────────────────────────────────┐
│                    NeuralNexus Client                 │
│  client_entry.py → leader discovery → stub connect   │
│  rpc_client.py   → all gRPC calls                    │
│  ui_actions.py   → menu-driven UI                    │
└──────────────────────────┬───────────────────────────┘
                           │ gRPC (insecure)
                           ▼
┌──────────────────────────────────────────────────────┐
│              NeuralNexus Server Node (×N)             │
│  ┌─────────┬───────────┬────────────┬───────┬──────┐ │
│  │  Auth   │ Materials │Assignments │Queries│  LLM │ │
│  └────┬────┴─────┬─────┴──────┬─────┴───┬───┴──┬───┘ │
│       └──────────┴────────────┴─────────┘      │     │
│                    Handlers Layer               │     │
│              (business logic + DB)              │     │
│                                                 │     │
│  ┌─────────────────────────────────────────┐   │     │
│  │           Raft Consensus Engine          │   │     │
│  │  Node (state machine) + Timer            │   │     │
│  │  leader_append_log → replicate → apply   │   │     │
│  └─────────────────────────────────────────┘   │     │
│                                                 │     │
│  ┌─────────────────────────────────────────┐   │     │
│  │  SQLite (lms.db)                         │   │     │
│  │  users, courses, materials, assignments, │   │     │
│  │  queries, raft_logs, state_info, …       │   │     │
│  └─────────────────────────────────────────┘   │     │
│                                      Phi-3 LLM ◄─────┘
└──────────────────────────────────────────────────────┘
         ↕ Raft RPCs (requestVote / appendEntries)
    Other cluster nodes
```

---

## License

Private repository. All rights reserved.
