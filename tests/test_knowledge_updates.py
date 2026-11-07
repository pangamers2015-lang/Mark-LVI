import json
from memory import cognitive_store as s,cognitive_runtime as rt,knowledge_updates as ku
def setup(p):
 old=(s.DB_PATH,rt._DB);s.DB_PATH=p/"cognitive.sqlite3";rt._DB=s.DB_PATH;assert rt.initialize();return old
def restore(o):s.DB_PATH,rt._DB=o
def test_idempotent_and_searchable(tmp_path):
 o=setup(tmp_path)
 try:
  x={"id":"test-one","category":"knowledge","title":"Yon fact","content":"GitHub knowledge imports use SQLite.","status":"approved"}
  a=ku.apply_update(x);b=ku.apply_update(x)
  assert a["ok"] and not a["already_applied"] and b["already_applied"]
  assert any(z["id"]==a["memory_id"] for z in rt.retrieve("GitHub SQLite",semantic=False))
 finally:restore(o)
def test_personality_updates_self_model(tmp_path):
 o=setup(tmp_path)
 try:
  x={"id":"personality-one","category":"personality","key":"tone","title":"Tone","content":"Be clear and patient.","status":"approved"}
  assert ku.apply_update(x)["ok"]
  assert "Be clear and patient." in s.format_cognitive_context()
 finally:restore(o)
def test_rejects_draft_and_bad_id():
 assert not ku.validate({"id":"draft","category":"knowledge","title":"x","content":"y","status":"draft"})[0]
 assert not ku.validate({"id":"../x","category":"knowledge","title":"x","content":"y","status":"approved"})[0]
def test_immutable_id(tmp_path):
 o=setup(tmp_path)
 try:
  x={"id":"fixed-id","category":"knowledge","title":"Fact","content":"One","status":"approved"}
  assert ku.apply_update(x)["ok"] and not ku.apply_update(dict(x,content="Two"))["ok"]
 finally:restore(o)
def test_folder_sync(tmp_path):
 o=setup(tmp_path)
 try:
  d=tmp_path/"updates";d.mkdir()
  (d/"ok.json").write_text(json.dumps({"id":"sync-one","category":"procedure","title":"Procedure","content":"Validate first.","status":"approved"}),encoding="utf8")
  (d/"draft.json").write_text(json.dumps({"id":"sync-draft","category":"knowledge","title":"Draft","content":"No","status":"draft"}),encoding="utf8")
  a=ku.sync_approved_updates(d);b=ku.sync_approved_updates(d)
  assert a["applied"]==1 and a["skipped"]==1 and b["already_applied"]==1
 finally:restore(o)
