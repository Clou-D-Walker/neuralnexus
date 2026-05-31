# API Overview — NeuralNexus gRPC Services

All services are defined in `proto/Lms.proto` and served on the port specified by the `NODE_PORT` environment variable (default: **50052**).

Authentication is passed as gRPC metadata: `("authorization", <AES-encrypted-token>)`.

---

## Auth Service

### `studentLogin`
Authenticate as a student.

**Request**
```protobuf
LoginRequest { string username; string password; }
```
> Password must be **SHA-256 hashed** by the client before sending.

**Response**
```protobuf
LoginResponse { string token; string error; string code; }
```
`code` = `"200"` on success, `"401"` on bad credentials, `"500"` on server error.

---

### `facultyLogin`
Authenticate as an instructor. Same message types as `studentLogin`.

---

## Materials Service

### `courseMaterialUpload` *(client-streaming)*
Upload a course material file in 1 MB chunks.
**Auth:** Instructor only.

**Request stream**
```protobuf
UploadCourseMaterialRequest {
  string course;    // course UUID
  string name;      // display name
  string term;      // e.g. "20241"
  string filename;  // original filename
  bytes  data;      // file chunk
  string created;
}
```

**Response**
```protobuf
UploadCourseMaterialResponse { string size; string error; string code; }
```

---

### `getCourseContents`
List all materials for a course.
**Auth:** Any valid token.

**Request**
```protobuf
GetCourseContentsRequest { string course; string term; }
```

**Response** — `data` is a JSON string:
```json
{ "contents": [{ "id": "<uuid>", "name": "Lecture 1", "file": "lec1.pdf" }] }
```

---

### `getCourseMaterial` *(server-streaming)*
Download a material file by ID in 1 MB chunks.
**Auth:** Any valid token.

**Request**
```protobuf
GetCourseMaterialRequest { string course; string term; string name; }
```
> `name` is the material UUID returned from `getCourseContents`.

**Response stream**
```protobuf
GetCourseMaterialResponse { string name; string filename; bytes data; string error; }
```

---

## Assignments Service

### `submitAssignment` *(client-streaming)*
Submit an assignment file.
**Auth:** Student only.

**Request stream**
```protobuf
SubmitAssignmentRequest {
  string studentid;
  string course;
  string assignment_name;
  bytes  data;
  string filename;
}
```

**Response**
```protobuf
SubmitAssignmentResponse { string code; string error; }
```

---

### `getSubmittedAssignment` *(server-streaming)*
Download all student submissions as a ZIP archive.
**Auth:** Instructor only.

**Request**
```protobuf
GetSubmittedAssignmentsRequest { string course; string assignment_name; }
```

**Response stream**
```protobuf
GetSubmittedAssignmentsResponse { bytes data; string error; string code; }
```

---

## Queries Service

### `createQuery`
Post an academic question.
**Auth:** Student only.

```protobuf
CreateQueryRequest  { string query; string course; }
CreateQueryResponse { string error; string code;  }
```

---

### `getQueries`
Retrieve all queries for a course.
**Auth:** Any valid token.

**Response** — `queries` is a JSON string:
```json
{
  "q": [
    {
      "id": "<uuid>",
      "query_text": "What is a semaphore?",
      "posted_by": "alice",
      "reply": "A semaphore is …",
      "replied_by": "prof_bob"
    }
  ]
}
```

---

### `answerQuery`
Provide an answer to a student query.
**Auth:** Instructor only.

```protobuf
AnswerQueryRequest  { string qid; string answer; }
AnswerQueryResponse { string error; string code; }
```

---

## LLM Service

### `askLlm` *(bidirectional streaming)*
Chat with the Phi-3 AI tutor.
**Auth:** Any valid token.

```protobuf
AskLlmRequest  { string query; }
AskLlmResponse { string reply; string error; string code; }
```

The model is restricted to Science & Technology topics. Off-topic queries receive a denial response.

---

## Raft Service

Internal service used for cluster coordination. Not called by the client directly.

| RPC | Purpose |
|---|---|
| `requestVote` | Candidate solicits votes during leader election |
| `appendEntries` | Leader replicates log entries / sends heartbeats |
| `getLeader` | Any node can be polled to find the current leader UUID |

### `getLeader`
Used by the client during startup to discover which node is the current leader.

```protobuf
GetLeaderRequest  { int32 ack; }
GetLeaderResponse { string node_id; }
```
`node_id` is empty if no leader has been elected yet.
