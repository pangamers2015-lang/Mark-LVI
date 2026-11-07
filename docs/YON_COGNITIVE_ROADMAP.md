# Yon — Cognitive Architecture Roadmap

Branch: `feature/behavioral-preferences`

This roadmap is incremental. Existing voice, audio, UI, Gemini Live, action discovery,
and personal-memory systems must remain intact. Do not replace them as part of this work.

## Architecture principles

- SQLite is the durable source of truth; Obsidian is an optional human-facing view.
- Keep personal profile, explicit lessons, conversation continuity, and cognitive records
  separate but connected. Do not duplicate existing stores.
- Every knowledge item must retain its source and a state: confirmed, hypothesis, stale,
  or contested. Never invent a numeric confidence score.
- A goal/checkpoint is evidence of recorded progress, not proof that a task succeeded.
- Verify current repository/runtime state before resuming interrupted work.
- No destructive or consequential action without the required user approval.
- Add dependencies only when a working feature actually needs them.

## Delivery phases

| Phase | Scope | Status |
|---|---|---|
| 0 | Audit existing memory, continuity, learning, and work journal | Completed (code inspection only; no runtime test claimed) |
| 1 | Structured cognitive SQLite store: self-model, evidence-aware memories, goals, checkpoints | Implemented remotely; local runtime test pending |
| 1b | Load compact cognitive state into each new model session | Implemented remotely; local runtime test pending |
| 2 | Connect task lifecycle and work journal to durable checkpoints | Planned |
| 3 | Retrieval improvements (SQLite FTS5 first; evaluate embeddings only after baseline tests) | Planned |
| 4 | Memory hierarchy, consolidation, stale/conflict handling, and provenance policies | Planned |
| 5 | Metacognitive review: identify missing evidence, freshness, and need for research | Planned |
| 6 | Persistent objective planning, dependencies, safe resume, and progress reporting | Planned |
| 7 | Research/learning/verification workflows and self-correction | Planned |
| 8 | Supervisor and specialist workers (planner, researcher, executor, reviewer) | Planned |
| 9 | Optional Obsidian views/export; never a runtime dependency | Planned |

## Current implementation details

- `memory/continuity_store.py` remains the turn-by-turn conversation history.
- `memory/learning_store.py` remains the explicit correction/lesson store.
- `memory/memory_manager.py` remains the existing user profile and session-summary store.
- `memory/cognitive_store.py` adds the structured self-model, knowledge records,
  goals, and checkpoints in `memory/cognitive.sqlite3`.
- `main.py` adds the compact cognitive context when building a new Live session prompt.
- SQLite and all current Phase 1 code use Python's standard library. No new package install
  is required for this phase.

## Validation gates

Before declaring a phase complete:
1. Pull the remote branch locally without overwriting local changes.
2. Run Python syntax/import checks in the user's environment.
3. Run isolated SQLite tests against a temporary database.
4. Verify existing voice startup, conversation, reconnection, and shutdown behavior.
5. Verify personal databases and API keys remain untracked and unchanged.
6. Record exactly what passed and what remains untested.

A remote commit or static code inspection is not a runtime test.
