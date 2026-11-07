"""Curated knowledge imports into Yon's existing SQLite memory."""
import hashlib,json,re,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from memory import cognitive_store as store
CATEGORIES={"knowledge","procedure","personality","identity"}
SLUG=re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
def _db():
 p=Path(store.DB_PATH);p.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(str(p),timeout=10)
 c.execute("CREATE TABLE IF NOT EXISTS knowledge_update_receipts(update_id TEXT PRIMARY KEY,digest TEXT NOT NULL,memory_id INTEGER,applied_at TEXT NOT NULL)")
 return c
def validate(x):
 if not isinstance(x,dict):return False,"JSON object required."
 uid=str(x.get("id","")).strip();cat=str(x.get("category","")).strip().lower()
 if not SLUG.fullmatch(uid):return False,"Invalid stable update id."
 if cat not in CATEGORIES:return False,"Invalid category."
 if not str(x.get("title","")).strip() or len(str(x.get("title","")))>240:return False,"Invalid title."
 content=str(x.get("content","")).strip()
 if not content or len(content)>12000:return False,"Invalid content length."
 if x.get("status")!="approved":return False,"Only approved updates can be imported."
 if cat in {"personality","identity"} and (not SLUG.fullmatch(str(x.get("key","")).strip().lower()) or len(content)>1800):return False,"Personality/identity requires a valid key and <=1800 characters."
 if len(str(x.get("evidence","")))>4000:return False,"Evidence too long."
 return True,""
def apply_update(x):
 ok,err=validate(x)
 if not ok:return {"ok":False,"error":err}
 if not store.initialize():return {"ok":False,"error":"SQLite initialization failed."}
 uid=x["id"];digest=hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 with _db() as c:old=c.execute("SELECT digest,memory_id FROM knowledge_update_receipts WHERE update_id=?",(uid,)).fetchone()
 if old:
  if old[0]!=digest:return {"ok":False,"error":"Update ID immutable; use a new ID for changed content."}
  return {"ok":True,"already_applied":True,"memory_id":old[1],"update_id":uid}
 evidence=str(x.get("evidence","")).strip();cat=x["category"]
 mid=store.add_memory(f"{x['title'].strip()}: {x['content'].strip()}",level="semantic",source="github_knowledge_update:"+uid,state="confirmed" if evidence else "hypothesis",evidence=evidence,validated=bool(evidence))
 if not mid:return {"ok":False,"error":"SQLite memory write failed."}
 if cat in {"personality","identity"} and not store.set_identity(f"learned_{cat}_{x['key'].lower().strip()}",x["content"].strip(),source="github_knowledge_update:"+uid):return {"ok":False,"error":"Self-model write failed."}
 now=datetime.now(timezone.utc).isoformat(timespec="seconds")
 try:
  with _db() as c:c.execute("INSERT INTO knowledge_update_receipts VALUES(?,?,?,?)",(uid,digest,mid,now))
 except sqlite3.IntegrityError:
  with _db() as c:row=c.execute("SELECT digest,memory_id FROM knowledge_update_receipts WHERE update_id=?",(uid,)).fetchone()
  if not row or row[0]!=digest:return {"ok":False,"error":"Receipt verification failed."}
  mid=row[1]
 return {"ok":True,"already_applied":False,"memory_id":mid,"update_id":uid,"category":cat}
def sync_approved_updates(root=None):
 folder=Path(root) if root else Path(__file__).resolve().parents[1]/"knowledge"/"updates"
 counts={"applied":0,"already_applied":0,"skipped":0};errors=[]
 if not folder.exists():return {"ok":True,**counts}
 for f in sorted(folder.glob("*.json")):
  try:r=apply_update(json.loads(f.read_text(encoding="utf-8")))
  except Exception as e:r={"ok":False,"error":type(e).__name__+": "+str(e)}
  if not r.get("ok"):counts["skipped"]+=1;errors.append(f"{f.name}: {r.get('error')}")
  elif r.get("already_applied"):counts["already_applied"]+=1
  else:counts["applied"]+=1
 return {"ok":not errors,**counts,"errors":errors}
