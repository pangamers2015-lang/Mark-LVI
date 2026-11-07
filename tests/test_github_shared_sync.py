from __future__ import annotations

import hashlib
import sqlite3

from memory import github_shared_sync as sync


def _blob_sha(raw: bytes) -> str:
    return sync._git_blob_sha(raw)


def test_uploads_local_file_without_remote_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "SHARED_ROOT", tmp_path / "shared")
    monkeypatch.setattr(sync.store, "DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr(sync, "_LAST_SYNC", 0.0)
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "hello.txt").write_text("hello Yon", encoding="utf-8")
    uploaded = []
    monkeypatch.setattr(sync, "_remote_files", lambda: {})
    monkeypatch.setattr(
        sync, "_upload",
        lambda path, raw, sha: uploaded.append((path, raw, sha)) or {"content": {"sha": _blob_sha(raw)}},
    )

    result = sync.sync_shared_folder(force=True)

    assert result["ok"] is True
    assert result["uploaded"] == 1
    assert uploaded == [("hello.txt", b"hello Yon", None)]


def test_downloads_remote_file_to_local_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "SHARED_ROOT", tmp_path / "shared")
    monkeypatch.setattr(sync.store, "DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr(sync, "_LAST_SYNC", 0.0)
    remote = {"Oi Chat/saudacao.txt": _blob_sha(b"Ola, ChatGPT!")}
    monkeypatch.setattr(sync, "_remote_files", lambda: remote)
    monkeypatch.setattr(sync, "_download", lambda path: b"Ola, ChatGPT!")

    result = sync.sync_shared_folder(force=True)

    assert result["ok"] is True
    assert result["downloaded"] == 1
    assert (tmp_path / "shared" / "Oi Chat" / "saudacao.txt").read_text(encoding="utf-8") == "Ola, ChatGPT!"


def test_conflicting_first_sync_never_overwrites_either_side(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "SHARED_ROOT", tmp_path / "shared")
    monkeypatch.setattr(sync.store, "DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr(sync, "_LAST_SYNC", 0.0)
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "same.txt").write_text("local version", encoding="utf-8")
    remote = {"same.txt": _blob_sha(b"remote version")}
    monkeypatch.setattr(sync, "_remote_files", lambda: remote)
    monkeypatch.setattr(sync, "_download", lambda path: b"remote version")

    result = sync.sync_shared_folder(force=True)

    assert result["ok"] is False
    assert result["conflicts"] == ["same.txt"]
    assert (tmp_path / "shared" / "same.txt").read_text(encoding="utf-8") == "local version"


def test_ignores_non_text_files_and_hidden_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "SHARED_ROOT", tmp_path / "shared")
    monkeypatch.setattr(sync, "_LAST_SYNC", 0.0)
    (tmp_path / "shared" / ".private").mkdir(parents=True)
    (tmp_path / "shared" / ".private" / "secret.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "shared" / "image.png").write_bytes(b"not text")
    (tmp_path / "shared" / "visible.txt").write_text("ok", encoding="utf-8")

    files = sync._local_files()

    assert list(files) == ["visible.txt"]
