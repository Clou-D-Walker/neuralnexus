import sqlite3
import hashlib
import uuid

def h(p):
    return hashlib.sha256(p.encode()).hexdigest()

def uid():
    return str(uuid.uuid4())

DB = r'C:\Surya\Creed\dis-lms\neuralnexus\server\lms.db'

conn = sqlite3.connect(DB)
conn.execute("PRAGMA foreign_keys = OFF")

# Clear all tables first
tables = [
    'assignment_submissions', 'materials', 'queries', 'raft_logs',
    'assignments', 'course_enrolled', 'courses', 'users', 'roles',
    'node_discovery', 'state_info'
]
for t in tables:
    conn.execute(f'DELETE FROM {t}')
print("Tables cleared.")

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
role_student    = uid()
role_instructor = uid()
conn.execute('INSERT INTO roles(id,name) VALUES(?,?)', (role_student,    'Student'))
conn.execute('INSERT INTO roles(id,name) VALUES(?,?)', (role_instructor, 'Instructor'))
print(f"Roles seeded.")

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
u_santosh = uid()
u_sreeja  = uid()
u_surya   = uid()
u_abhi    = uid()

conn.execute(
    'INSERT INTO users(id,username,email,password,role_id,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',
    (u_santosh, 'santosh',    'santosh.a@iiits.in',  h('admin123'), role_instructor)
)
conn.execute(
    'INSERT INTO users(id,username,email,password,role_id,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',
    (u_sreeja,  'sreeja',     'sreeja.sr@iiits.in',  h('admin123'), role_instructor)
)
conn.execute(
    'INSERT INTO users(id,username,email,password,role_id,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',
    (u_surya,   'surya',      'suryasujit.n22@iiits.in', h('surya123'), role_student)
)
conn.execute(
    'INSERT INTO users(id,username,email,password,role_id,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',
    (u_abhi,    'abhi',       'abhinash.t22@iiits.in',   h('abhi123'),  role_student)
)
print("Users seeded: santosh (Instructor), sreeja (Instructor), surya (Student), abhi (Student)")

# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------

# Fixed UUID — must match hardcoded COURSE_ID in rpc_client.py
c_gnn  = '8d313659-2360-44a2-9ab0-57dbd1ddc201'
c_ai   = uid()
c_ir   = uid()
c_web  = uid()
c_dsa  = uid()

courses = [
    (c_gnn, 'Graph Neural Networks',          'GNN01', u_santosh),
    (c_ai,  'Artificial Intelligence',         'AI01',  u_sreeja),
    (c_ir,  'Information Retrieval',           'IR01',  u_sreeja),
    (c_web, 'Web Development',                 'WDB01', u_sreeja),
    (c_dsa, 'Data Structures and Algorithms',  'DSA01', u_sreeja),
]
for cid, name, code, instructor in courses:
    conn.execute(
        'INSERT INTO courses(id,course_name,course_code,instructor_id,created_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)',
        (cid, name, code, instructor)
    )
print(f"Courses seeded: GNN01 (santosh) | AI01 IR01 WDB01 DSA01 (sreeja)")

# ---------------------------------------------------------------------------
# Enrol students in all courses
# ---------------------------------------------------------------------------
for cid, *_ in courses:
    for uid_ in (u_surya, u_abhi):
        conn.execute(
            'INSERT INTO course_enrolled(course_id,user_id,created_at) VALUES(?,?,CURRENT_TIMESTAMP)',
            (cid, uid_)
        )
print("Students surya & abhi enrolled in all 5 courses.")

# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

# Fixed UUID — must match hardcoded ASSIGNMENT_ID in rpc_client.py
a_gnn1 = '2d8f2298-beac-4a27-b70a-c1da56600993'

assignments = [
    # GNN01 — Graph Neural Networks (santosh)
    (a_gnn1, 'Assignment 1 – Graph Convolution Basics',
     '2026-03-31 23:59:59',
     'Implement a basic Graph Convolutional Network and evaluate it on the Cora dataset.',
     c_gnn),
    (uid(), 'Assignment 2 – Message Passing Networks',
     '2026-05-15 23:59:59',
     'Design and train a Message Passing Neural Network for molecular property prediction.',
     c_gnn),
    (uid(), 'Assignment 3 – Graph Attention Networks',
     '2026-07-31 23:59:59',
     'Compare GAT and GCN architectures on a node classification benchmark.',
     c_gnn),

    # AI01 — Artificial Intelligence (sreeja)
    (uid(), 'Assignment 1 – Search Algorithms',
     '2026-02-28 23:59:59',
     'Implement BFS, DFS, A* and compare their performance on a maze-solving problem.',
     c_ai),
    (uid(), 'Assignment 2 – Knowledge Representation',
     '2026-04-30 23:59:59',
     'Build a simple expert system using propositional logic and forward chaining.',
     c_ai),
    (uid(), 'Assignment 3 – Constraint Satisfaction',
     '2026-06-30 23:59:59',
     'Solve the N-Queens problem using backtracking with constraint propagation.',
     c_ai),
    (uid(), 'Assignment 4 – Reinforcement Learning',
     '2026-08-31 23:59:59',
     'Train a Q-learning agent to navigate a grid-world environment.',
     c_ai),

    # IR01 — Information Retrieval (sreeja)
    (uid(), 'Assignment 1 – Inverted Index',
     '2026-02-15 23:59:59',
     'Build an inverted index from a corpus of 500+ documents and support Boolean queries.',
     c_ir),
    (uid(), 'Assignment 2 – TF-IDF Ranking',
     '2026-04-15 23:59:59',
     'Implement TF-IDF scoring and rank documents for a set of test queries.',
     c_ir),
    (uid(), 'Assignment 3 – Query Expansion',
     '2026-06-15 23:59:59',
     'Use WordNet-based query expansion and measure the impact on precision and recall.',
     c_ir),
    (uid(), 'Assignment 4 – Neural IR',
     '2026-08-15 23:59:59',
     'Fine-tune a BERT-based model for passage re-ranking on the MS MARCO dataset.',
     c_ir),

    # WDB01 — Web Development (sreeja)
    (uid(), 'Assignment 1 – HTML & CSS Portfolio',
     '2026-02-20 23:59:59',
     'Build a responsive personal portfolio website using only HTML5 and CSS3.',
     c_web),
    (uid(), 'Assignment 2 – JavaScript DOM Manipulation',
     '2026-04-20 23:59:59',
     'Create an interactive to-do list application using vanilla JavaScript and LocalStorage.',
     c_web),
    (uid(), 'Assignment 3 – REST API Design',
     '2026-06-20 23:59:59',
     'Design and implement a RESTful API for a bookstore using Node.js and Express.',
     c_web),
    (uid(), 'Assignment 4 – Full Stack Application',
     '2026-08-20 23:59:59',
     'Build a full-stack web app with authentication, a database, and a React frontend.',
     c_web),

    # DSA01 — Data Structures and Algorithms (sreeja)
    (uid(), 'Assignment 1 – Sorting Algorithms',
     '2026-03-10 23:59:59',
     'Implement Merge Sort, Quick Sort and Heap Sort; analyse time and space complexity.',
     c_dsa),
    (uid(), 'Assignment 2 – Tree Traversals',
     '2026-05-10 23:59:59',
     'Implement in-order, pre-order, post-order and level-order traversals iteratively.',
     c_dsa),
    (uid(), 'Assignment 3 – Graph Algorithms',
     '2026-07-10 23:59:59',
     'Implement Dijkstra and Bellman-Ford; compare on weighted directed graphs.',
     c_dsa),
    (uid(), 'Assignment 4 – Dynamic Programming',
     '2026-09-10 23:59:59',
     'Solve the 0/1 Knapsack, Longest Common Subsequence, and Matrix Chain Multiplication problems.',
     c_dsa),
]

for aid, name, due, desc, cid in assignments:
    conn.execute(
        'INSERT INTO assignments(id,name,due_date,description,course_id,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',
        (aid, name, due, desc, cid)
    )
print(f"Assignments seeded: {len(assignments)} total across 5 courses.")

# ---------------------------------------------------------------------------
# Node discovery (3-node Raft cluster)
# ---------------------------------------------------------------------------
nodes = [
    ('ee1f954b-99ab-48e2-95fd-730e4aec2489', 'localhost', '50052'),
    ('de3b3357-8c1f-4911-910e-977d2ff02611', 'localhost', '50053'),
    ('becedead-63a4-48a8-a017-e284cd02d21e', 'localhost', '50054'),
]
for nid, host, port in nodes:
    conn.execute(
        'INSERT INTO node_discovery(id,host,port,created_at) VALUES(?,?,?,CURRENT_TIMESTAMP)',
        (nid, host, port)
    )
print("Node discovery seeded: 3 nodes (50052, 50053, 50054)")

# ---------------------------------------------------------------------------
# Raft state_info
# ---------------------------------------------------------------------------
conn.execute('INSERT INTO state_info(term,idx,voted_for) VALUES(0,0,NULL)')
print("State info seeded.")

conn.commit()
conn.close()

print("\n=== Seed complete ===")
print()
print("Instructors:")
print("  santosh   santosh.a@iiits.in   admin123  ->  GNN01")
print("  sreeja    sreeja.sr@iiits.in   admin123  ->  AI01, IR01, WDB01, DSA01")
print()
print("Students:")
print("  surya     suryasujit.n22@iiits.in  surya123  →  enrolled in all 5 courses")
print("  abhi      abhinash.t22@iiits.in    abhi123   →  enrolled in all 5 courses")
print()
print("Courses & assignments:")
print("  GNN01  Graph Neural Networks         3 assignments")
print("  AI01   Artificial Intelligence       4 assignments")
print("  IR01   Information Retrieval         4 assignments")
print("  WDB01  Web Development               4 assignments")
print("  DSA01  Data Structures & Algorithms  4 assignments")
