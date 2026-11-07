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
- Specialist role contracts: planner, researcher, executor and reviewer, coordinated by the active model and existing action registry.
- Optional second-brain bridge: the active coordinator can consult a local Ollama model and critically review its independent response; it never assumes Ollama is running.
- Knowledge association engine: conservative lexical or already-available embedding matches create provenance-labelled `possible_related_to` edges. These are suggestions, not confirmed facts.

## Obsidian knowledge workspace
When `YON_OBSIDIAN_VAULT` is configured, Yon generates a navigable, read-only knowledge workspace under `Yon/Generated/`:
- `Home.generated.md`: entry dashboard with links, totals and evidence-reading rules.
- `Cognitive Memories.generated.md`: chronological overview of exported memories.
- `Memory N.generated.md`: one durable note per SQLite memory, with YAML metadata, tags, evidence and backlinks.
- `Memory Graph.generated.md`: graph index and explicit relationship links.
- `Objectives.generated.md`: objectives and their current lifecycle state.
- `Indexes/By Level.generated.md`: working, episodic, semantic and consolidated memory.
- `Indexes/By Evidence State.generated.md`: confirmed, hypothesis, stale and contested records.
- `Indexes/By Source.generated.md`: memories grouped by origin.
- `Indexes/Objectives by Status.generated.md`: objectives grouped by lifecycle status.

Existing root-level generated memory filenames are preserved so existing Obsidian wikilinks continue to work. The bridge writes atomically and never edits user-authored notes. It does not depend on Obsidian internals or make Obsidian a runtime requirement.

**Important architecture distinction:** Obsidian is the human-facing map and navigation layer. Its indexes make the knowledge easier to inspect and understand, but they do not themselves make model reasoning faster. Retrieval speed and relevance come from SQLite indexes/FTS5, optional embeddings, and the cognitive retrieval policies. SQLite remains the authoritative store; generated Markdown can be rebuilt from it.

## Preservation and data safety
This complements existing voice, UI, provider, action, profile-memory, learning, conversation-continuity and work-journal systems. It does not replace them.
Runtime databases remain local under memory/ and must not be committed. API keys, local journals and user data remain untracked. A checkpoint is a record, not proof that an operation succeeded. Interrupted operations must be inspected before resuming.

## Optional framework installation
The core cognitive runtime and lexical retrieval use Python's standard library.
Optional packages are listed in requirements-cognitive.txt:
- LangGraph: supervisor workflow orchestration.
- NetworkX: graph analysis.
- Sentence Transformers: local semantic embeddings; model downloads on first use.
- Ollama: separate local application, not a Python package; optional second-model consultation uses its local HTTP API. Configure YON_LOCAL_MODEL with an installed model name and optionally YON_OLLAMA_URL if Ollama is not listening on its default local endpoint.
- Obsidian: optional viewer for generated Markdown. Set YON_OBSIDIAN_VAULT to the vault's full filesystem path. Open Obsidian Graph View and include the Yon/Generated folder to inspect the connected knowledge graph. Yon does not read Obsidian internals; SQLite remains authoritative.

Install optional Python packages from the project root with: `pip install -r requirements-cognitive.txt`.
Sentence Transformers installs PyTorch and can use substantial disk and RAM. It is optional; Yon continues with FTS5 if it is unavailable. Embeddings load lazily on the first semantic indexing request, not during application startup.

## Validation status
Remote changes are not proof of local runtime success. The Obsidian workspace refreshes when the bridge is invoked and a valid vault path is configured. Pull the branch and start Yon to load the updated code; confirm the generated dashboard appears in the configured vault during normal use.
