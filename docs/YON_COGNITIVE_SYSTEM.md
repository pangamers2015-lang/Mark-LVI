# Yon — Integrated Cognitive System

## Included capabilities
- Self-model: identity, purpose, principles and limitations stored in SQLite.
- Hierarchical memory: working, episodic, semantic and consolidated records.
- Provenance: source, evidence, state and validation timestamp; no invented confidence scores.
- Retrieval: SQLite FTS5 plus optional local sentence embeddings.
- Knowledge graph: durable SQLite relations and optional NetworkX graph analysis.
- Metacognition: objective, uncertainty, evidence, research and verification checklist.
- Objectives: priorities, lifecycle updates, prerequisite dependencies with cycle checks, and progress checkpoints.
- Background work: start, completion and interrupted-recovery checkpoints are persisted.
- Supervisor: assess → retrieve → plan → review, with LangGraph and a standard-library fallback.
- Specialist role contracts: planner, researcher, executor and reviewer, coordinated by the
  active model and existing action registry.
- Optional second-brain bridge: the active coordinator can consult a local Ollama model and
  critically review its independent response; it never assumes Ollama is running.
- Agent interface: active model can call yon_brain to search/store memories, validate evidence,
  create/list goals, checkpoint work, connect concepts and assess complex requests.
- Live integration: each fresh voice session receives a unified cognitive context; incoming
  user requests are evaluated for explicit learning cues and active task intent.

## Preservation and data safety
This complements existing voice, UI, provider, action, profile-memory, learning,
conversation-continuity and work-journal systems. It does not replace them.
Runtime databases remain local under memory/ and must not be committed. API keys,
local journals and user data remain untracked. A checkpoint is a record, not proof
that an operation succeeded. Interrupted operations must be inspected before resuming.

## Optional framework installation
The core cognitive runtime and lexical retrieval use Python's standard library.
Optional packages are listed in requirements-cognitive.txt:
- LangGraph: supervisor workflow orchestration.
- NetworkX: graph analysis.
- unittest suite: isolated regression tests are included under tests/test_cognitive_runtime.py.
- Sentence Transformers: local semantic embeddings; model downloads on first use.
- Ollama: separate local application, not a Python package; optional second-model consultation
  uses its local HTTP API. Configure YON_LOCAL_MODEL with an installed model name and optionally
  YON_OLLAMA_URL if Ollama is not listening on its default local endpoint.

Install from the project root with: pip install -r requirements-cognitive.txt
Sentence Transformers installs PyTorch and can use substantial disk and RAM. It is
optional; Yon continues with FTS5 if it is unavailable. Embeddings load lazily on
the first semantic indexing request, not during application startup.

## Validation status
Remote code changes and static inspection do not establish local runtime success.
After pulling, validate Python syntax/imports, SQLite operations on a temporary DB,
tool discovery, voice startup, reconnection, shutdown and preservation of personal data.
