# Development Guide — NeuralNexus

> **Interface:** NeuralNexus is a **terminal/CLI application**. There is no web or desktop frontend. All user interaction is through the menu-driven `client_entry.py` script running in a CMD/terminal window.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.9+ | Tested on 3.14 |
| pip | Comes with Python |
| Virtual environment | `env/` at project root |
| Rust / MSVC (optional) | Only needed if building pydantic-core from source |
| CUDA GPU (optional) | For hardware-accelerated LLM inference |
| Phi-3 GGUF model (optional) | Place at `server/Model/Phi-3-Context-Obedient-RAG-Q4_K_M.gguf`. Server runs without it — LLM features are disabled gracefully. |

---

## Environment Setup

```cmd
REM From the project root (dis-lms/)
env\Scripts\activate

REM Install server dependencies
pip install -r neuralnexus\server\requirements.txt

REM Generate gRPC Python code (server)
cd neuralnexus\server
call generate_proto_code.bat
cd ..\..

REM Generate gRPC Python code (client)
cd neuralnexus\client
call gen_proto_code.bat
cd ..\..
```

---

## Node Configuration

Each node reads its configuration from a `.env` file. The path is controlled by the `ENV_FILE` environment variable (defaults to `.env` in the working directory).

| Node | ENV_FILE | NODE_ID |
|---|---|---|
| Node 1 | `neuralnexus/server/.env` | `ee1f954b-99ab-48e2-95fd-730e4aec2489` |
| Node 2 | `neuralnexus/server/node2/.env` | `de3b3357-8c1f-4911-910e-977d2ff02611` |
| Node 3 | `neuralnexus/server/node3/.env` | `becedead-63a4-48a8-a017-e284cd02d21e` |

**Important:** All nodes must share the **same `AES_SECRET`** so tokens issued by any node are valid cluster-wide.

### What is NODE_ID and where does it come from?

`NODE_ID` is a plain UUID that ties a running server process to its row in the `node_discovery` SQLite table. Raft uses it to identify which node is which during leader election and log replication.

**It is not a secret** (it can be public), but it must be consistent: the value in `.env` must exactly match the `id` column in `node_discovery` for that node.

**When you clone this repo fresh**, the databases are not committed. You need to:

1. **Generate 3 UUIDs** — one per node:
   ```cmd
   python -c "import uuid; print(uuid.uuid4()); print(uuid.uuid4()); print(uuid.uuid4())"
   ```

2. **Generate one `AES_SECRET`** shared by all nodes:
   ```cmd
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Edit `seed_db.py`** — replace the three UUIDs in the `nodes` list with your generated ones.

4. **Run `seed_db.py`** to create and seed the database:
   ```cmd
   cd neuralnexus\server
   python seed_db.py
   copy lms.db node2\lms.db
   copy lms.db node3\lms.db
   ```

5. **Create `.env` files** from the examples — copy the template and fill in your values:
   ```cmd
   copy neuralnexus\server\.env.example neuralnexus\server\.env
   copy neuralnexus\server\node2\.env.example neuralnexus\server\node2\.env
   copy neuralnexus\server\node3\.env.example neuralnexus\server\node3\.env
   ```
   Then edit each file: set `AES_SECRET` to the same value in all three, and set `NODE_ID` in each to the matching UUID from step 1.

> If you just want to run the demo locally without changing UUIDs, the `seed_db.py` already has fixed UUIDs pre-filled. Just run it, copy the DB, copy `.env.example` → `.env`, fill in `AES_SECRET`, and go.

---

## Running the Full Demo (4 terminals)

The easiest way is `start_cluster.bat` — it opens all three nodes in separate windows with a single double-click:

```cmd
start_cluster.bat
```

This launches `start_node1.bat`, `start_node2.bat`, and `start_node3.bat` each in their own CMD window (1 second apart). Once all three are running, open a fourth terminal for the client:

```cmd
start_client.bat
```

Alternatively you can launch each bat individually if you want to watch one node at a time:

```cmd
REM Terminal 1
start_node1.bat

REM Terminal 2
start_node2.bat

REM Terminal 3
start_node3.bat

REM Terminal 4 (after ~2 s — wait for leader election)
start_client.bat
```

Each batch script sets `NODE_PORT`, `DB_PATH`, and `ENV_FILE` automatically, activates the venv, and starts the process from the correct working directory.

### Running with a single node (quick testing)

You can run just **Node 1 + the client** for quick local testing:

```cmd
start_node1.bat
REM (new terminal)
start_client.bat
```

With only one node the Raft majority calculation resolves to 1 (self-vote is enough), so Node 1 elects itself leader immediately and all operations — including writes — succeed. This is useful for development but does **not** demonstrate fault-tolerance or distributed consensus. Use all 3 nodes for any demo or interview.

### What each node prints on start

```
WARNING:root:llm_handler: llama_cpp not installed — LLM features will be disabled.
[NeuralNexus] Server listening on port 50052
[Raft] Leader timeout: 318 ms
```

After ~300–400 ms one node will win the election. The client will discover it automatically.

### Demo credentials

| Role | Username | Email | Password | Courses |
|---|---|---|---|---|
| Instructor | `santosh` | santosh.a@iiits.in | `admin123` | GNN01 |
| Instructor | `sreeja` | sreeja.sr@iiits.in | `admin123` | AI01, IR01, WDB01, DSA01 |
| Student | `surya` | suryasujit.n22@iiits.in | `surya123` | all 5 |
| Student | `abhi` | abhinash.t22@iiits.in | `abhi123` | all 5 |

---

## Manual Cluster Launch (without batch scripts)

```cmd
REM Node 1
cd neuralnexus\server
set NODE_PORT=50052 && set DB_PATH=lms.db && set ENV_FILE=.env
python server_entry.py

REM Node 2  (new terminal)
cd neuralnexus\server
set NODE_PORT=50053 && set DB_PATH=node2\lms.db && set ENV_FILE=node2\.env
python server_entry.py

REM Node 3  (new terminal)
cd neuralnexus\server
set NODE_PORT=50054 && set DB_PATH=node3\lms.db && set ENV_FILE=node3\.env
python server_entry.py

REM Client  (new terminal)
cd neuralnexus\client
python client_entry.py
```

---

## Database Management

All data lives in `neuralnexus/server/lms.db` (SQLite). Because the DB is not committed to the repo, `seed_db.py` is the single source of truth for the initial dataset. Every change — new users, courses, assignments — is made by editing `seed_db.py` and re-running it.

> After any change to `seed_db.py`, always copy the updated DB to the other two nodes:
> ```cmd
> cd neuralnexus\server
> python seed_db.py
> copy lms.db node2\lms.db
> copy lms.db node3\lms.db
> ```

---

### How `seed_db.py` works

1. Connects to `lms.db`
2. **Clears every table** (DELETE FROM each table in dependency order)
3. Re-inserts all data from scratch
4. Commits and closes

This means it is always a **full reset** — there is no partial update. To add or change anything, edit the relevant section in the file and re-run.

---

### Adding a new instructor

Find the **Users** section in `seed_db.py` and add a new entry:

```python
u_alice = uid()
conn.execute(
    'INSERT INTO users(id,username,email,password,role_id,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',
    (u_alice, 'alice', 'alice@iiits.in', h('alice123'), role_instructor)
)
```

- `uid()` generates a fresh UUID
- `h('alice123')` SHA-256 hashes the password
- `role_instructor` is already defined earlier in the script

---

### Adding a new student

Same as above but use `role_student`:

```python
u_bob = uid()
conn.execute(
    'INSERT INTO users(id,username,email,password,role_id,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',
    (u_bob, 'bob', 'bob@iiits.in', h('bob123'), role_student)
)
```

---

### Adding a new course

Find the **Courses** section and add a new tuple to the `courses` list:

```python
c_ml = uid()

courses = [
    # ... existing courses ...
    (c_ml, 'Machine Learning', 'ML01', u_alice),   # instructor = alice
]
```

The format is `(course_id, course_name, course_code, instructor_user_id)`.

---

### Adding assignments to a course

Find the **Assignments** section and append to the `assignments` list:

```python
assignments = [
    # ... existing assignments ...

    # ML01 — Machine Learning (alice)
    (uid(), 'Assignment 1 – Linear Regression',
     '2026-04-30 23:59:59',
     'Implement linear regression from scratch and evaluate on a housing price dataset.',
     c_ml),
    (uid(), 'Assignment 2 – Classification',
     '2026-06-30 23:59:59',
     'Compare Logistic Regression, SVM and Decision Trees on the Iris dataset.',
     c_ml),
]
```

The format is `(assignment_id, name, due_date, description, course_id)`.  
Use `uid()` for new assignments. The `due_date` format is `'YYYY-MM-DD HH:MM:SS'`.

> **Fixed UUIDs:** `a_gnn1` (the first GNN assignment) and `c_gnn` (the GNN course) use hardcoded UUIDs because they are referenced in `neuralnexus/client/rpc_client.py`. Do not change these.

---

### Enrolling students in a course

Find the **Enrol students** section. Students are currently enrolled in all courses in a loop. To enrol a specific student in only specific courses, replace the loop with explicit inserts:

```python
# Enrol bob only in ML01 and DSA01
for cid in (c_ml, c_dsa):
    conn.execute(
        'INSERT INTO course_enrolled(course_id,user_id,created_at) VALUES(?,?,CURRENT_TIMESTAMP)',
        (cid, u_bob)
    )
```

---

### Current dataset at a glance

| Course | Code | Instructor | Assignments |
|---|---|---|---|
| Graph Neural Networks | GNN01 | santosh | 3 |
| Artificial Intelligence | AI01 | sreeja | 4 |
| Information Retrieval | IR01 | sreeja | 4 |
| Web Development | WDB01 | sreeja | 4 |
| Data Structures and Algorithms | DSA01 | sreeja | 4 |

Both students (`surya`, `abhi`) are enrolled in all 5 courses.

---

## Project Layout Reference

```
dis-lms/
├── neuralnexus/
│   ├── server/
│   │   ├── server_entry.py         ← START HERE for server
│   │   ├── services/               ← gRPC servicers
│   │   ├── handlers/               ← business logic
│   │   ├── consensus/
│   │   │   └── raft_node.py        ← full Raft implementation
│   │   ├── database/
│   │   │   ├── schema.py           ← table creation
│   │   │   └── db_methods.py       ← SQL queries
│   │   ├── security/
│   │   │   ├── settings.py         ← .env config
│   │   │   ├── token_manager.py    ← AES-256 token
│   │   │   └── access_control.py  ← gRPC decorators
│   │   ├── proto/
│   │   │   └── Lms.proto           ← source of truth for all RPCs
│   │   └── core/
│   │       ├── imports.py
│   │       └── utils.py
│   └── client/
│       ├── client_entry.py         ← START HERE for client
│       ├── rpc_client.py           ← all gRPC calls
│       ├── ui_actions.py           ← menu actions
│       ├── menu_renderer.py        ← generic menu loop
│       └── session_manager.py      ← stub registry singleton
├── docs/
│   ├── architecture.md
│   ├── system-design.md
│   ├── api-overview.md
│   └── development-guide.md       ← you are here
├── start_cluster.bat              ← launches all 3 nodes at once
├── start_node1.bat                ← Node 1 only (port 50052)
├── start_node2.bat                ← Node 2 only (port 50053)
├── start_node3.bat                ← Node 3 only (port 50054)
├── start_client.bat               ← CLI client
└── README.md
```

---

## Enabling AI / LLM Features

By default the server starts with LLM features **disabled** — it prints a warning and continues normally:

```
WARNING:root:llm_handler: llama_cpp not installed — LLM features will be disabled.
```

All other features (auth, materials, assignments, queries, Raft) work regardless. To enable the AI tutoring feature you need to do two things.

### Step 1 — Install `llama-cpp-python`

This package compiles a C++ backend, so a C++ build tool is required first.

**Windows prerequisite:** Install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) — select the **"Desktop development with C++"** workload.

**CPU-only install (simplest):**
```cmd
env\Scripts\activate
pip install llama-cpp-python
```

**GPU-accelerated install (CUDA — requires CUDA Toolkit):**
```cmd
env\Scripts\activate
set CMAKE_ARGS=-DGGML_CUDA=on
pip install llama-cpp-python --force-reinstall --no-cache-dir
```

### Step 2 — Download the model

The server process runs from the `neuralnexus/server/` directory, so the model must be placed at:

```
neuralnexus/server/Model/Phi-3-Context-Obedient-RAG-Q4_K_M.gguf
```

This path is relative to `neuralnexus/server/` — **not** the repo root. Create the `Model/` folder inside `neuralnexus/server/` if it does not exist:

```cmd
mkdir neuralnexus\server\Model
```

Then download the `Q4_K_M` variant (~2.4 GB) from Hugging Face and place it there:
```
https://huggingface.co/bartowski/Phi-3-Context-Obedient-RAG-GGUF
```

The exact file name must be `Phi-3-Context-Obedient-RAG-Q4_K_M.gguf` — this is what `handlers/llm_handler.py` looks for at startup.

### Step 3 — Nothing else to change

No code changes are needed. `llm_handler.py` detects `llama_cpp` and the model file at runtime and loads the model on first use. The AI tutoring option in the client menu will become functional automatically.

---

## Extending the System

### Adding a new service

1. Add messages and a service to `proto/Lms.proto`.
2. Regenerate proto code (`generate_proto_code.bat`).
3. Create `services/new_service.py` implementing the servicer class.
4. Create `handlers/new_handler.py` with business logic.
5. If the operation mutates state, add a dispatch entry to the handler's `*_map` dict and call `node.leader_append_log("module.function", args)` in the servicer.
6. Register the servicer in `server_entry.py`.

### Modifying Raft timing

Edit the constants in `consensus/raft_node.py`:

```python
class Timer:
    HEARTBEAT_INTERVAL_MS = 100  # leader heartbeat frequency

# Election timeout: seeded-random per node in get_random_leader_timeout()
def _get_random_leader_timeout(node_id: str) -> int:
    random.seed(node_id)
    return random.randint(200, 400)  # adjust range here
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `No leader found` | No server is running | Start at least one server node |
| `UNAUTHENTICATED` on all calls | Token expired or wrong AES_SECRET | Re-login; verify all nodes share the same AES_SECRET |
| `PERMISSION_DENIED` | Wrong role for endpoint | Log in with the correct account type |
| `Majority of nodes are down` | Less than majority of nodes reachable | Start more nodes |
| `state_info` error at startup | Table not seeded | Run `create_everything()` (called automatically by `server_entry.py`) |
| LLM does not respond | `llama_cpp` not installed or model file missing | See [Enabling AI / LLM Features](#enabling-ai--llm-features) above |
