"""Integrated cognitive runtime for Yon."""
from __future__ import annotations
import re, sqlite3, threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from memory import cognitive_store as store

_DB = Path(__file__).resolve().parent / "cognitive.sqlite3"
_LOCK = threading.RLock()
_EMBEDDER = None
_EMBEDDER_ERROR = ""
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _db():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB), timeout=15)
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS memory_relations(
      id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL,
      target_id INTEGER NOT NULL, relation TEXT NOT NULL,
      evidence TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
      UNIQUE(source_id,target_id,relation));
    CREATE INDEX IF NOT EXISTS idx_memory_relations_source ON memory_relations(source_id);
    CREATE TABLE IF NOT EXISTS memory_embeddings(
      memory_id INTEGER PRIMARY KEY, model TEXT NOT NULL, vector BLOB NOT NULL,
      dimensions INTEGER NOT NULL, updated_at TEXT NOT NULL);
    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
      content,evidence,source,content='memories',content_rowid='id');
    CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
      INSERT INTO memories_fts(rowid,content,evidence,source)
      VALUES(new.id,new.content,new.evidence,new.source); END;
    CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
      INSERT INTO memories_fts(memories_fts,rowid,content,evidence,source)
      VALUES('delete',old.id,old.content,old.evidence,old.source); END;
    CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
      INSERT INTO memories_fts(memories_fts,rowid,content,evidence,source)
      VALUES('delete',old.id,old.content,old.evidence,old.source);
      INSERT INTO memories_fts(rowid,content,evidence,source)
      VALUES(new.id,new.content,new.evidence,new.source); END;
    """)
    conn.execute("""INSERT INTO memories_fts(rowid,content,evidence,source)
      SELECT m.id,m.content,m.evidence,m.source FROM memories m
      WHERE NOT EXISTS(SELECT 1 FROM memories_fts f WHERE f.rowid=m.id)""")
    return conn

def initialize():
    if not store.initialize(): return False
    try:
        with _LOCK, closing(_db()) as conn: conn.commit()
        return True
    except sqlite3.Error as exc:
        print(f"[YonBrain] Initialization failed: {exc}")
        return False

def remember(content, level="semantic", source="user", state="hypothesis", evidence=""):
    if state == "confirmed" and not str(evidence or "").strip(): return None
    if not initialize(): return None
    memory_id = store.add_memory(content,level=level,source=source,state=state,evidence=evidence,
                                 validated=(state=="confirmed"))
    if memory_id and _EMBEDDER is not None: index_memory(memory_id)
    return memory_id

def validate_memory(memory_id,state,evidence):
    if state=="confirmed" and not str(evidence or "").strip(): return False
    return store.set_memory_state(memory_id,state,evidence)

def relate(source_id,target_id,relation,evidence=""):
    relation=re.sub(r"[^a-zA-Z0-9_ -]","",str(relation or "")).strip()[:80]
    if not relation or source_id==target_id: return False
    try:
        with _LOCK, closing(_db()) as conn, conn:
            count=conn.execute("SELECT COUNT(*) FROM memories WHERE id IN (?,?)",
                               (int(source_id),int(target_id))).fetchone()[0]
            if count!=2: return False
            conn.execute("""INSERT OR IGNORE INTO memory_relations
              (source_id,target_id,relation,evidence,created_at) VALUES(?,?,?,?,?)""",
              (int(source_id),int(target_id),relation,str(evidence)[:2000],_now()))
        return True
    except (sqlite3.Error,TypeError,ValueError) as exc:
        print(f"[YonBrain] Relation write failed: {exc}")
        return False

def _embedder():
    global _EMBEDDER,_EMBEDDER_ERROR
    if _EMBEDDER is not None: return _EMBEDDER
    if _EMBEDDER_ERROR: return None
    try:
        from sentence_transformers import SentenceTransformer
        _EMBEDDER=SentenceTransformer(_MODEL_NAME,device="cpu")
        return _EMBEDDER
    except Exception as exc:
        _EMBEDDER_ERROR=str(exc)
        return None

def index_memory(memory_id):
    model=_embedder()
    if model is None: return False
    try:
        item=next((x for x in store.search_memories("",limit=500)
                   if int(x["id"])==int(memory_id)),None)
        if not item: return False
        import numpy as np
        vector=model.encode([item["content"]],normalize_embeddings=True)[0]
        with _LOCK,closing(_db()) as conn,conn:
            conn.execute("""INSERT INTO memory_embeddings
              (memory_id,model,vector,dimensions,updated_at) VALUES(?,?,?,?,?)
              ON CONFLICT(memory_id) DO UPDATE SET model=excluded.model,
              vector=excluded.vector,dimensions=excluded.dimensions,updated_at=excluded.updated_at""",
              (int(memory_id),_MODEL_NAME,np.asarray(vector,dtype="float32").tobytes(),
               len(vector),_now()))
        return True
    except Exception as exc:
        print(f"[YonBrain] Embedding index failed: {exc}")
        return False

def _semantic_search(query,limit):
    model=_embedder()
    if model is None: return []
    try:
        import numpy as np
        q=model.encode([query],normalize_embeddings=True)[0]
        with _LOCK,closing(_db()) as conn:
            rows=conn.execute("""SELECT e.memory_id,e.vector,e.dimensions,m.level,m.content,
              m.source,m.state,m.evidence,m.created_at,m.validated_at
              FROM memory_embeddings e JOIN memories m ON m.id=e.memory_id
              WHERE e.model=? LIMIT 3000""",(_MODEL_NAME,)).fetchall()
        scored=[]
        for row in rows:
            vec=np.frombuffer(row[1],dtype="float32",count=row[2])
            if len(vec)==len(q): scored.append((float(np.dot(q,vec)),row))
        scored.sort(key=lambda x:x[0],reverse=True)
        return [{"id":r[0],"level":r[3],"content":r[4],"source":r[5],"state":r[6],
          "evidence":r[7],"created_at":r[8],"validated_at":r[9],
          "score":round(score,4),"match":"semantic"} for score,r in scored[:limit]]
    except Exception as exc:
        print(f"[YonBrain] Semantic search failed: {exc}")
        return []

def retrieve(query="",limit=8,semantic=True):
    limit=max(1,min(int(limit),30)); lexical=[]
    if initialize() and str(query or "").strip():
        terms=[x for x in re.findall(r"[\wÀ-ÿ]+",query) if len(x)>1]
        expr=" OR ".join('"'+t.replace('"','""')+'"' for t in terms[:12])
        if expr:
            try:
                with _LOCK,closing(_db()) as conn:
                    rows=conn.execute("""SELECT m.id,m.level,m.content,m.source,m.state,m.evidence,
                      m.created_at,m.validated_at,bm25(memories_fts) FROM memories_fts
                      JOIN memories m ON m.id=memories_fts.rowid
                      WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts) LIMIT ?""",
                      (expr,limit*3)).fetchall()
                lexical=[{"id":r[0],"level":r[1],"content":r[2],"source":r[3],"state":r[4],
                  "evidence":r[5],"created_at":r[6],"validated_at":r[7],
                  "score":float(-r[8]),"match":"fts"} for r in rows]
            except sqlite3.Error: lexical=[]
    if not lexical:
        lexical=[dict(x,match="keyword") for x in store.search_memories(query,limit=limit)]
    semantic_hits=_semantic_search(query,limit*2) if semantic and query else []
    merged={}
    for item in lexical+semantic_hits:
        key=int(item["id"])
        if key not in merged: merged[key]=item
        elif item.get("match")=="semantic": merged[key]["semantic_score"]=item.get("score")
    result=list(merged.values())
    result.sort(key=lambda x:(x["state"]=="confirmed",x["level"]=="consolidated",
      x.get("semantic_score",x.get("score",0)),x["id"]),reverse=True)
    return result[:limit]

def record_user_turn(text):
    value=" ".join(str(text or "").split()).strip()
    if len(value)<12: return
    lower=value.casefold()
    cues=("lembre disso","lembre-se","guarde isso","aprenda","quero que aprenda",
      "sempre que eu pedir","não faça novamente","nao faca novamente","o correto é",
      "o correto e","corrigindo","da próxima vez","da proxima vez","remember this","next time")
    if any(cue in lower for cue in cues):
        remember(value,level="semantic",source="explicit_user_instruction",
          state="confirmed",evidence="Explicit user instruction or correction.")
    task_cues=("faça ","faca ","implemente","crie ","pesquise","resolva",
      "continue","vamos construir","build ","implement ")
    if any(cue in lower for cue in task_cues):
        remember(value,level="working",source="current_user_request",
          state="hypothesis",evidence="Task intent; outcome not yet verified.")

def save_task_checkpoint(summary,next_step="",goal_id=None,status="in_progress",evidence=""):
    return store.save_checkpoint(summary,next_step,goal_id,status,evidence)

def _metacognitive_rules():
    return """[YON METACOGNITIVE OPERATING PROTOCOL]
Identify the objective and constraints. Separate facts, assumptions, hypotheses and unknowns.
Retrieve relevant lessons and project state. Check freshness and evidence. Research missing or
time-sensitive facts with available tools. For multi-step work track objectives, dependencies
and checkpoints. Inspect actual outcomes; distinguish attempted, changed, installed and runtime-
tested. Never claim success without evidence. Do not expose private chain-of-thought; report
concise decisions, evidence and uncertainty. Never blindly replay interrupted operations.
Confirm before destructive or consequential actions."""

def build_context(query="",max_chars=6200):
    parts=[]
    try:
        from memory.continuity_store import format_recent_context
        recent=format_recent_context(limit=18,max_chars=3200)
        if recent: parts.append(recent)
    except Exception as exc: print(f"[YonBrain] Continuity bridge unavailable: {exc}")
    try:
        from memory.learning_store import format_learning_for_prompt
        lessons=format_learning_for_prompt(limit=12)
        if lessons: parts.append(lessons)
    except Exception as exc: print(f"[YonBrain] Learning bridge unavailable: {exc}")
    structured=store.format_cognitive_context(max_chars=3600)
    if structured: parts.append(structured)
    hits=retrieve(query,limit=6) if query else []
    if hits:
        parts.append("[RELEVANT RETRIEVED MEMORIES]")
        parts.extend(f"- [{x['level']} | {x['state']} | source={x['source']} | "
          f"match={x.get('match','unknown')}] {x['content']}" for x in hits)
    parts.append(_metacognitive_rules())
    return "\n\n".join(parts)[:max(1000,int(max_chars))]

def assess_request(request):
    text=str(request or "").strip(); lower=text.casefold()
    research=any(x in lower for x in ("atual","hoje","agora","último","ultimo",
      "preço","preco","pesquise","fonte","recent","latest","current"))
    multi=len(text.split())>18 or any(x in lower for x in
      ("implemente","desenvolva","projeto","planeje","construa"))
    return {"objective":text[:1200],"needs_research":research,"multi_step":multi,
      "must_retrieve_memory":True,"must_verify_result":True,"unknowns":[],
      "decision":"research" if research else ("plan" if multi else "respond_or_act")}

def run_cognitive_cycle(request):
    state={"request":str(request or ""),"assessment":{},"memories":[],"plan":[],"review":""}
    def assess(s): s["assessment"]=assess_request(s["request"]); return s
    def retrieve_node(s): s["memories"]=retrieve(s["request"],limit=6); return s
    def plan_node(s):
        a=s["assessment"]
        s["plan"]=(["Confirm objective and constraints","Retrieve applicable memory and lessons",
          "Research missing or time-sensitive facts","Choose the safest feasible action",
          "Verify result and record evidence"] if a["multi_step"] or a["needs_research"]
          else ["Check relevant memory","Answer or act","Verify factual claims"])
        return s
    def review_node(s):
        s["review"]="No outcome has been verified yet; this is a plan, not completion."
        return s
    try:
        from langgraph.graph import END,START,StateGraph
        from typing_extensions import TypedDict
        class BrainState(TypedDict,total=False):
            request:str
            assessment:dict
            memories:list
            plan:list
            review:str
        graph=StateGraph(BrainState)
        for name,node in (("assess",assess),("retrieve",retrieve_node),
          ("plan",plan_node),("review",review_node)): graph.add_node(name,node)
        graph.add_edge(START,"assess"); graph.add_edge("assess","retrieve")
        graph.add_edge("retrieve","plan"); graph.add_edge("plan","review")
        graph.add_edge("review",END)
        return graph.compile().invoke(state)
    except ImportError:
        for node in (assess,retrieve_node,plan_node,review_node): state=node(state)
        return state
    except Exception as exc:
        print(f"[YonBrain] Supervisor fallback: {exc}")
        for node in (assess,retrieve_node,plan_node,review_node): state=node(state)
        return state

def graph_summary(limit=30):
    try:
        with _LOCK,closing(_db()) as conn:
            rows=conn.execute("SELECT source_id,target_id,relation FROM memory_relations "
              "ORDER BY id DESC LIMIT ?",(max(1,min(int(limit),100)),)).fetchall()
        try:
            import networkx as nx
            graph=nx.DiGraph()
            graph.add_edges_from((a,b,{"relation":rel}) for a,b,rel in rows)
            return {"nodes":graph.number_of_nodes(),"edges":graph.number_of_edges(),
              "components":nx.number_weakly_connected_components(graph)}
        except ImportError:
            return {"nodes":len({x for r in rows for x in r[:2]}),"edges":len(rows),
              "components":None,"note":"Install networkx for graph analytics."}
    except sqlite3.Error: return {"nodes":0,"edges":0,"components":None}


def add_goal_dependency(goal_id, depends_on_goal_id):
    """Add a prerequisite edge, rejecting missing goals and dependency cycles."""
    try:
        goal_id, depends_on_goal_id = int(goal_id), int(depends_on_goal_id)
        if goal_id == depends_on_goal_id: return False
        goals = {int(x["id"]) for x in store.list_goals(include_finished=True, limit=100)}
        if goal_id not in goals or depends_on_goal_id not in goals: return False
        with _LOCK, closing(_db()) as conn:
            edges = conn.execute("SELECT goal_id,depends_on_goal_id FROM goal_dependencies").fetchall()
        adjacency = {}
        for source, target in edges: adjacency.setdefault(int(source), set()).add(int(target))
        pending, visited = [depends_on_goal_id], set()
        while pending:
            current = pending.pop()
            if current == goal_id: return False
            if current in visited: continue
            visited.add(current)
            pending.extend(adjacency.get(current, ()))
        with _LOCK, closing(_db()) as conn, conn:
            conn.execute("INSERT OR IGNORE INTO goal_dependencies(goal_id,depends_on_goal_id,created_at) VALUES(?,?,?)",
                         (goal_id, depends_on_goal_id, _now()))
        return True
    except (sqlite3.Error, TypeError, ValueError): return False

def goal_dependency_map():
    try:
        with _LOCK, closing(_db()) as conn:
            rows = conn.execute("SELECT goal_id,depends_on_goal_id FROM goal_dependencies").fetchall()
        result = {}
        for goal_id, dependency_id in rows:
            result.setdefault(int(goal_id), []).append(int(dependency_id))
        return result
    except sqlite3.Error: return {}

def consolidate_memory(memory_id, evidence):
    """Promote a confirmed memory only when explicit consolidation evidence exists."""
    evidence = str(evidence or "").strip()
    if not evidence: return False
    try:
        with _LOCK, closing(_db()) as conn, conn:
            cur = conn.execute("UPDATE memories SET level='consolidated',evidence=?,validated_at=? "
                "WHERE id=? AND state='confirmed'", (evidence[:4000],_now(),int(memory_id)))
            return cur.rowcount > 0
    except (sqlite3.Error,TypeError,ValueError): return False
