# Architecture Report — NeuralNexus Transformation

## A. Old vs New Structure

### Old Structure (`AOS-LMS-M3/`)

```
AOS-LMS-M3/
├── lms-server/
│   ├── main.py
│   ├── Services/
│   │   ├── auth.py
│   │   ├── materials.py
│   │   ├── assignments.py
│   │   ├── queries.py
│   │   ├── llm.py
│   │   └── raft.py
│   ├── Helpers/
│   │   ├── auth.py
│   │   ├── materials.py
│   │   ├── assignments.py
│   │   ├── queries.py
│   │   ├── llm.py
│   │   ├── raft.py          ← 3-line stub, unused
│   │   ├── users.py         ← empty
│   │   └── common.py        ← empty
│   ├── Raft/
│   │   ├── node.py          ← 709 lines
│   │   └── timer.py         ← 82 lines ALL commented out (dead code)
│   ├── Database/
│   │   ├── creation_scripts.py
│   │   └── methods.py
│   ├── Config/
│   │   ├── secrets.py
│   │   ├── key_manager.py
│   │   └── decorators.py
│   ├── Importers/
│   │   ├── common_imports.py
│   │   └── common_methods.py
│   └── protos/
│       └── Lms.proto
└── lms-client/
    ├── main.py
    ├── menu.py
    ├── functions.py
    ├── grpc_calls.py
    ├── imports.py
    └── action.py            ← empty
```

### New Structure (`neuralnexus/`)

```
neuralnexus/
├── server/
│   ├── server_entry.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── materials_service.py
│   │   ├── assignments_service.py
│   │   ├── queries_service.py
│   │   ├── llm_service.py
│   │   └── raft_service.py
│   ├── handlers/
│   │   ├── auth_handler.py
│   │   ├── materials_handler.py
│   │   ├── assignments_handler.py
│   │   ├── queries_handler.py
│   │   └── llm_handler.py
│   ├── consensus/
│   │   └── raft_node.py
│   ├── database/
│   │   ├── schema.py
│   │   └── db_methods.py
│   ├── security/
│   │   ├── settings.py
│   │   ├── token_manager.py
│   │   └── access_control.py
│   ├── proto/
│   │   └── Lms.proto
│   └── core/
│       ├── imports.py
│       └── utils.py
└── client/
    ├── client_entry.py
    ├── rpc_client.py
    ├── ui_actions.py
    ├── menu_renderer.py
    └── session_manager.py

docs/
├── architecture.md
├── system-design.md
├── api-overview.md
└── development-guide.md

README.md
```

---

## B. Renaming Summary

### Server

| Old Name | New Name | Reason |
|---|---|---|
| `AOS-LMS-M3/lms-server/` | `neuralnexus/server/` | Brand identity; cleaner hierarchy |
| `main.py` | `server_entry.py` | Descriptive entry-point name |
| `Services/` | `services/` | PEP 8 lowercase package names |
| `Services/auth.py` | `services/auth_service.py` | Indicates it's a gRPC servicer |
| `Services/materials.py` | `services/materials_service.py` | Same |
| `Services/assignments.py` | `services/assignments_service.py` | Same |
| `Services/queries.py` | `services/queries_service.py` | Same |
| `Services/llm.py` | `services/llm_service.py` | Same |
| `Services/raft.py` | `services/raft_service.py` | Same |
| `Helpers/` | `handlers/` | Industry-standard term for business logic layer |
| `Helpers/auth.py` | `handlers/auth_handler.py` | Clearer role |
| `Helpers/materials.py` | `handlers/materials_handler.py` | Same |
| `Helpers/assignments.py` | `handlers/assignments_handler.py` | Same |
| `Helpers/queries.py` | `handlers/queries_handler.py` | Same |
| `Helpers/llm.py` | `handlers/llm_handler.py` | Same |
| `Helpers/raft.py` | *(removed)* | Was a 3-line unused stub |
| `Helpers/users.py` | *(removed)* | Empty file |
| `Helpers/common.py` | *(removed)* | Empty file |
| `Raft/` | `consensus/` | Communicates algorithm-agnostic intent |
| `Raft/node.py` | `consensus/raft_node.py` | Explicit module name |
| `Raft/timer.py` | *(removed)* | 82 lines all commented-out (dead code) |
| `Database/` | `database/` | PEP 8 lowercase |
| `Database/creation_scripts.py` | `database/schema.py` | Standard naming |
| `Database/methods.py` | `database/db_methods.py` | More descriptive |
| `Config/` | `security/` | Reflects actual purpose (auth/crypto/settings) |
| `Config/secrets.py` | `security/settings.py` | Standard pydantic-settings naming |
| `Config/key_manager.py` | `security/token_manager.py` | Describes what it manages |
| `Config/decorators.py` | `security/access_control.py` | Describes the access-control purpose |
| `Importers/` | `core/` | Standard name for shared infrastructure |
| `Importers/common_imports.py` | `core/imports.py` | Shorter |
| `Importers/common_methods.py` | `core/utils.py` | Standard utility module name |
| `protos/` | `proto/` | Singular noun convention |

### Client

| Old Name | New Name | Reason |
|---|---|---|
| `AOS-LMS-M3/lms-client/` | `neuralnexus/client/` | Brand identity |
| `main.py` | `client_entry.py` | Descriptive entry-point name |
| `menu.py` | `menu_renderer.py` | Describes the rendering responsibility |
| `functions.py` | `ui_actions.py` | Communicates these are UI-layer actions |
| `grpc_calls.py` | `rpc_client.py` | Protocol-agnostic name |
| `imports.py` | `session_manager.py` | Describes the GrpcHelper stub-registry role |
| `action.py` | *(removed)* | Empty file |

---

## C. Design Decisions

### 1. `pydantic.v1 → pydantic-settings`
The original code used `from pydantic.v1 import BaseSettings`, which is the deprecated v1 compatibility shim. Updated to use the standalone `pydantic-settings` package which is the correct approach for Pydantic v2.

### 2. `state_info` table added to schema
The original `creation_scripts.py` omitted the `state_info` table even though `Raft/node.py` read and wrote it. This was a silent gap. The new `database/schema.py` creates and seeds this table in `create_everything()`.

### 3. Dead code removed
- `Raft/timer.py` (82 lines, entirely commented out) — removed.
- `Helpers/raft.py`, `Helpers/users.py`, `Helpers/common.py`, `lms-client/action.py` — all empty stubs removed.
- `main.py` Pydantic model definitions (Students, Course, Faculty) — large commented-out blocks removed.

### 4. Unique RAFT constraint added to `raft_logs`
The original `CREATE TABLE` for `raft_logs` lacked the `UNIQUE (idx, term)` constraint even though follower inserts used `ON CONFLICT(idx, term) DO NOTHING`. Added to schema.

### 5. `NODE_PORT` environment variable
The original server always bound to port `50052`. The new `server_entry.py` reads `NODE_PORT` from the environment, making it trivial to run multiple nodes on the same machine without code changes.

### 6. `get_all_assignments → get_all_submissions`
The original name `get_all_assignments` was ambiguous (it retrieved *submissions*, not assignment definitions). Renamed to `get_all_submissions` with a backward-compat alias.

### 7. `Chat() → create_chat_session()`
The original factory function `Chat()` looked like a class. Renamed to `create_chat_session()` which communicates intent. Legacy alias retained.

---

## D. Improvements Made

| Category | Improvement |
|---|---|
| Code quality | PEP 8 lowercase package names throughout |
| Code quality | Type hints added to all handler and utility functions |
| Code quality | Docstrings added to every module, class, and public function |
| Code quality | Dead code and empty files removed |
| Code quality | `print()` debugging replaced with `logging` in consensus layer |
| Functionality | `state_info` table now created automatically |
| Functionality | `NODE_PORT` configurable via environment variable |
| Functionality | `UNIQUE (idx, term)` constraint explicitly in `raft_logs` schema |
| Architecture | Clear layer separation: services → handlers → database |
| Architecture | `security/` package groups all auth/crypto concerns |
| Documentation | Full Mermaid diagrams for Raft, election, LLM, and auth flows |
| Documentation | Development guide with cluster setup, seeding, and troubleshooting |
| Branding | All project names, module names, and print messages updated to **NeuralNexus** |

---

## E. Validation

All modules validated with the project's virtual environment (`env/`):

```
✅ database.schema          — create_everything() runs without error
✅ database.db_methods      — all SQL functions import cleanly
✅ core.utils               — all utility functions importable
✅ security.settings        — pydantic-settings reads .env correctly
✅ security.token_manager   — AES encrypt/decrypt round-trip verified
✅ security.access_control  — all three decorators import cleanly
✅ handlers.auth_handler    — imports cleanly
✅ handlers.materials_handler — imports cleanly
✅ handlers.assignments_handler — imports cleanly
✅ handlers.queries_handler — imports cleanly
✅ proto (server)           — Lms_pb2 / Lms_pb2_grpc generated and importable
✅ services.auth_service    — imports cleanly
✅ services.materials_service — imports cleanly
✅ services.assignments_service — imports cleanly
✅ services.queries_service — imports cleanly
✅ services.raft_service    — imports cleanly
✅ consensus.raft_node      — Node() instantiates; node.state='F', correct peer count
✅ proto (client)           — Lms_pb2 / Lms_pb2_grpc generated and importable
✅ session_manager          — GrpcHelper importable
✅ rpc_client               — all transport functions importable
✅ ui_actions               — all menu actions importable
✅ menu_renderer            — importable
⚠️  handlers.llm_handler    — deferred (requires llama_cpp_python + model file)
⚠️  services.llm_service    — deferred (requires handlers.llm_handler)
```

> The LLM handler is intentionally deferred — it loads the 4 GB Phi-3 GGUF model at import time, which requires both `llama-cpp-python` and the model file to be present.
