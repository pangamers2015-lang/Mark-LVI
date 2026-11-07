import base64

from memory import cognitive_runtime as brain
from memory import cognitive_store as store
from memory import github_inbox as inbox_module
from memory.github_inbox import (
    mark_startup_delivered,
    pending_startup_directives,
    process_inbox,
    pending_live_speech,
    mark_live_speech_delivered,
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



def test_remote_live_speech_is_queued_and_delivered_once(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "cognitive.sqlite3")
    monkeypatch.setattr(brain, "remember", lambda *args, **kwargs: 52)
    monkeypatch.setattr(
        inbox_module,
        "_fetch_remote_txt_files",
        lambda: [("speak-now.txt", "Fale 1 2 3".encode("utf-8"))],
    )
    monkeypatch.setattr(
        inbox_module,
        "_interpret",
        lambda text, filename: {
            "kind": "speak_once",
            "title": "Immediate speech",
            "memory": "The user requested a one-time spoken response.",
            "startup_instruction": "",
            "speech_text": "1, 2, 3.",
        },
    )

    result = inbox_module.process_remote_inbox()
    assert result["ok"] and result["processed"] == 1
    pending = pending_live_speech()
    assert len(pending) == 1
    assert pending[0]["speech_text"] == "1, 2, 3."

    assert mark_live_speech_delivered([pending[0]["id"]]) == 1
    assert pending_live_speech() == []


def test_remote_fetch_uses_branch_query_and_decodes_txt(monkeypatch):
    payload = base64.b64encode("Fale 1 2 3".encode("utf-8")).decode("ascii")
    seen = []

    def fake_github_json(url, etag=None):
        seen.append((url, etag))
        if "/contents/knowledge/inbox?" in url:
            return ([{
                "type": "file",
                "path": "knowledge/inbox/speak-now.txt",
                "size": 10,
            }], '"inbox-etag"', False)
        if "/contents/knowledge/inbox/speak-now.txt?" in url:
            return ({"encoding": "base64", "content": payload}, None, False)
        raise AssertionError("Unexpected GitHub API URL: " + url)

    monkeypatch.setattr(inbox_module, "_REMOTE_ETAG", None)
    monkeypatch.setattr(inbox_module, "_github_json", fake_github_json)
    monkeypatch.setattr(inbox_module, "GITHUB_REPOSITORY", "pangamers2015-lang/Mark-LVI")
    monkeypatch.setattr(inbox_module, "GITHUB_BRANCH", "main")

    documents = inbox_module._fetch_remote_txt_files()
    assert documents == [("speak-now.txt", "Fale 1 2 3".encode("utf-8"))]
    assert "ref=main" in seen[0][0]
    assert seen[0][1] is None



def test_changed_txt_revision_is_reprocessed_and_important_learning_is_announced(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    note = inbox / "lesson.txt"
    note.write_text("Primeira versão do conhecimento.", encoding="utf-8")
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "cognitive.sqlite3")
    remembered = []
    monkeypatch.setattr(
        brain, "remember",
        lambda content, **kwargs: remembered.append((content, kwargs)) or len(remembered)
    )

    first = process_inbox(
        inbox,
        interpreter=lambda text, filename: {
            "kind": "knowledge",
            "title": "Nota",
            "memory": "Primeira versão.",
        },
    )
    assert first["ok"] and first["processed"] == 1
    assert pending_live_speech() == []

    note.write_text("Versão corrigida: o ChatGPT ajuda o Yon.", encoding="utf-8")
    second = process_inbox(
        inbox,
        interpreter=lambda text, filename: {
            "kind": "knowledge",
            "title": "Novo conhecimento",
            "memory": "O ChatGPT ajuda o Yon desde o começo do projeto.",
            "notify_user": True,
            "notification_text": "Senhor, adquiri um novo conhecimento: o ChatGPT ajuda o Yon desde o começo do projeto.",
            "importance": "high",
        },
    )
    assert second["ok"] and second["processed"] == 1
    pending = pending_live_speech()
    assert len(pending) == 1
    assert "ChatGPT ajuda o Yon" in pending[0]["speech_text"]
    assert len(remembered) == 2

    again = process_inbox(
        inbox,
        interpreter=lambda *_: (_ for _ in ()).throw(AssertionError("same revision must not be reinterpreted")),
    )
    assert again["ok"] and again["already_processed"] == 1
    assert len(pending_live_speech()) == 1
