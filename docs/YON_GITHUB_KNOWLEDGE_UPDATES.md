# GitHub knowledge and personality updates

The `knowledge_update` action saves user-approved content directly to local SQLite and verifies retrieval before confirming. Curated JSON files in `knowledge/updates/` are tested by GitHub Actions in a temporary database and imported locally when Yon builds its next session context.

Fields: id (immutable slug), category (knowledge/procedure/personality/identity), title, content, status=approved; personality/identity also require key. Optional evidence is required for confirmed status; otherwise records remain hypotheses. Repeated imports do not duplicate records. Changed content requires a new ID.

Saved text is context, not executable code or authority over system, safety, privacy or approval rules. GitHub CI cannot write to local SQLite while Yon is closed: green CI means the isolated tests passed, while local import requires the local receipt and read-after-write verification.
