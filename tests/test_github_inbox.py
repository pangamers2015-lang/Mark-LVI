from memory import cognitive_runtime as brain
from memory import cognitive_store as store
from memory.github_inbox import (
    mark_startup_delivered,
    pending_startup_directives,
    process_inbox,
)


def test_inbox_import_is_idempotent_and_queues_one_time_startup(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "next.txt").write_text(
        "Na próxima inicialização, cumprimente e conte de 1 a 5.", encoding="utf-8"
    )
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "cognitive.sqlite3")
    monkeypatch.setattr(brain, "remember", lambda *args, **kwargs: 41)
    interpreter = lambda text, filename: {
        "kind": "startup_once",
        "title": "Next startup instruction",
        "memory": "Greet and count from one to five at the next startup.",
        "startup_instruction": "Greet the user in Portuguese and count from 1 to 5.",
    }

    first = process_inbox(inbox, interpreter=interpreter)
    assert first["ok"] and first["processed"] == 1
    pending = pending_startup_directives()
    assert len(pending) == 1
    assert "count from 1 to 5" in pending[0]["instruction"]

    second = process_inbox(inbox, interpreter=interpreter)
    assert second["ok"] and second["already_processed"] == 1
    assert len(pending_startup_directives()) == 1

    assert mark_startup_delivered([pending[0]["id"]]) == 1
    assert pending_startup_directives() == []
