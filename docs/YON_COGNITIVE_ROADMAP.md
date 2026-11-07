# Yon — Cognitive Architecture Roadmap

Branch: feature/behavioral-preferences

Existing voice, audio, UI, Gemini Live, providers, action discovery and personal
memory systems must remain intact. This work extends rather than replaces them.

## Architecture principles
- SQLite is the durable source of truth; Obsidian is an optional human-facing view.
- Existing profile, explicit lessons, turn continuity and work journal remain authoritative
  for their domains; cognitive records connect them without indiscriminate duplication.
- Knowledge retains source, evidence and state: confirmed, hypothesis, stale or contested.
- Never invent numeric confidence. A goal/checkpoint is not proof of success.
- Verify current repository/runtime state before resuming interrupted work.
- Add optional dependencies only where they enable a concrete capability.

## Implemented remotely
- Structured self-model, four memory levels, evidence-aware records, goals and checkpoints.
- Cognitive runtime with SQLite FTS5 retrieval, optional sentence embeddings, durable
  knowledge relations, optional NetworkX analytics, and metacognitive assessment.
- LangGraph supervisor workflow (assess → retrieve → plan → review), with stdlib fallback.
- yon_brain action exposing memory, validation, goals, checkpoints, relationships and reflection.
- Voice-session context bridges continuity, explicit lessons and cognitive state.
- User request observer stores explicit learning cues and working task intent.
- Background task completion writes an evidence-bearing checkpoint.
- Optional framework list in requirements-cognitive.txt.

## Still requires local validation
- Pull the remote branch and run syntax/import checks.
- Exercise SQLite/FTS5 and all CRUD paths against a temporary database.
- Verify action discovery and tool schema acceptance by the configured model.
- Verify voice startup, audio input/output, reconnection, shutdown and background-task lifecycle.
- Confirm local API keys, work journal, backups, project briefs and other user data remain untouched.

Remote implementation and static inspection are not runtime validation. Do not claim
the cognitive system is operational until the user's local tests pass.

## Next evolution after the integrated foundation
- Add explicit goal dependencies and lifecycle reconciliation with all background workers.
- Add selective memory consolidation and conflict/staleness resolution.
- Add batch embedding/index maintenance and semantic retrieval evaluation.
- Add specialist worker policies and permission-scoped execution through existing tools.
- Add optional Obsidian export/views; Obsidian must never become a runtime dependency.
