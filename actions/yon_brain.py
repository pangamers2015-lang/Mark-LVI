"""User-facing tools for Yon's integrated cognitive system."""
from memory import cognitive_store
from memory import cognitive_runtime as brain

def yon_brain(parameters: dict, player=None) -> str:
    p=parameters or {}; action=str(p.get("action","status")).strip().lower()
    try:
        if action=="remember":
            state=str(p.get("state","hypothesis")).lower()
            mid=brain.remember(p.get("content",""),level=str(p.get("level","semantic")).lower(),
                source=str(p.get("source","user_or_conversation")),state=state,
                evidence=str(p.get("evidence","")))
            return (f"Memory recorded with ID {mid} and state {state}. It is not confirmed "
                "unless evidence supports that state.") if mid else "I could not record that memory."
        if action=="search":
            hits=brain.retrieve(str(p.get("query","")),limit=8)
            return "Relevant memories:\n"+"\n".join(
                f"#{x['id']} [{x['level']} | {x['state']} | {x['source']}] {x['content']}"
                for x in hits) if hits else "No relevant structured memories were found."
        if action=="validate":
            ok=brain.validate_memory(int(p.get("memory_id",0)),str(p.get("state","confirmed")),
                str(p.get("evidence","")))
            return "Memory state updated with evidence." if ok else (
                "Could not update memory. Confirmed memories require explicit evidence.")
        if action=="goal_add":
            gid=cognitive_store.save_goal(str(p.get("title","")),str(p.get("description","")),
                int(p.get("priority",3)),"planned")
            if gid: brain._sync_obsidian()
            return f"Objective created with ID {gid}." if gid else "Could not create objective."
        if action=="goal_update":
            gid=int(p.get("goal_id",0))
            existing=next((g for g in cognitive_store.list_goals(include_finished=True,limit=100)
                           if int(g["id"])==gid),None)
            if not existing: return "Objective not found."
            status=str(p.get("state",existing["status"])).lower()
            title=str(p.get("title",existing["title"]))
            description=str(p.get("description",existing["description"]))
            priority=int(p.get("priority",existing["priority"]))
            updated=cognitive_store.save_goal(title,description,priority,status,goal_id=gid)
            if updated: brain._sync_obsidian()
            return f"Objective {gid} updated to {status}." if updated else "Could not update objective."
        if action=="goal_list":
            goals=cognitive_store.list_goals(limit=20)
            return "Active objectives:\n"+"\n".join(
                f"#{g['id']} P{g['priority']} [{g['status']}] {g['title']}: {g['description']}"
                for g in goals) if goals else "There are no active objectives."
        if action=="checkpoint":
            cid=brain.save_task_checkpoint(str(p.get("summary","")),str(p.get("next_step","")),
                int(p["goal_id"]) if p.get("goal_id") else None,
                str(p.get("state","in_progress")),str(p.get("evidence","")))
            return f"Checkpoint saved with ID {cid}." if cid else "Could not save checkpoint."
        if action=="depend":
            ok=brain.add_goal_dependency(int(p.get("goal_id",0)),int(p.get("depends_on_goal_id",0)))
            return "Goal dependency saved." if ok else "Dependency rejected: verify goal IDs and ensure the dependency graph has no cycle."
        if action=="index":
            ok=brain.index_memory(int(p.get("memory_id",0)))
            return "Memory indexed for semantic retrieval." if ok else "Semantic indexing unavailable or failed; install the optional embedding dependencies."
        if action=="consolidate":
            ok=brain.consolidate_memory(int(p.get("memory_id",0)),str(p.get("evidence","")))
            return "Confirmed memory consolidated." if ok else "Only a confirmed memory with explicit evidence can be consolidated."
        if action=="relate":
            ok=brain.relate(int(p.get("source_id",0)),int(p.get("target_id",0)),
                str(p.get("relation","related_to")),str(p.get("evidence","")))
            return "Memory relationship saved and Obsidian graph synchronized." if ok else "Could not create that relationship."
        if action=="graph_sync":
            result=brain._sync_obsidian()
            if result.get("ok"):
                return (f"Obsidian knowledge graph synchronized: {result.get('memory_count',0)} memories, "
                    f"{result.get('relationship_count',0)} links.")
            return "Obsidian graph sync unavailable: "+str(result.get("error",result.get("reason","Unknown error")))
        if action=="graph_status":
            graph=brain.graph_summary()
            return (f"Knowledge graph: {graph.get('nodes',0)} nodes, {graph.get('edges',0)} edges. "
                    "Automatic associations are tentative related-topic suggestions; Obsidian auto-sync "
                    "runs after memory/relationship changes when YON_OBSIDIAN_VAULT is configured.")
        if action=="reflect":
            r=brain.run_cognitive_cycle(str(p.get("request",""))); a=r.get("assessment",{})
            return (f"Cognitive assessment:\n- Decision: {a.get('decision')}\n"
                f"- Research needed: {a.get('needs_research')}\n- Multi-step: {a.get('multi_step')}\n"
                "- Plan:\n  "+"\n  ".join(r.get("plan",[]))+"\n"
                "- Specialist responsibilities:\n  "+"\n  ".join(
                    f"{x.get('role')}: {x.get('assignment')}" for x in r.get("specialists",[])
                )+"\n- "+str(r.get("review","")))
        if action=="obsidian_export":
            from memory.obsidian_bridge import export_cognitive_notes
            result=export_cognitive_notes(str(p.get("vault_path","")) or None)
            if not result.get("ok"):
                return "Obsidian export unavailable: "+str(result.get("error","Unknown error"))
            return (f"Exported {result.get('memory_count',0)} memories, {result.get('relationship_count',0)} relationships and "
                f"{result.get('goal_count',0)} objectives to the configured Obsidian vault: "
                +", ".join(result.get("files",[])))
        if action=="status":
            from importlib.util import find_spec
            goals=cognitive_store.list_goals(limit=100); graph=brain.graph_summary()
            dependency_installed=find_spec("sentence_transformers") is not None
            semantic_state=("model loaded" if brain._EMBEDDER is not None else
                "dependency installed; model loads on first semantic operation"
                if dependency_installed else "optional dependency not installed")
            return (f"Yon cognitive system initialized={brain.initialize()}; active_goals={len(goals)}; "
                f"graph_nodes={graph.get('nodes',0)}; graph_edges={graph.get('edges',0)}; "
                f"semantic_retrieval={semantic_state}.")
        return "Unknown action. Use status, remember, search, validate, goal_add, goal_update, goal_list, checkpoint, depend, index, consolidate, relate, graph_sync, graph_status, reflect or obsidian_export."
    except Exception as exc:
        return f"Yon cognitive tool failed safely: {type(exc).__name__}: {exc}"

TOOL={
"name":"yon_brain",
"description":("Manages Yon's persistent cognitive system: evidence-aware memories, automatic tentative knowledge associations, retrieval, "
"validation, objectives, checkpoints, knowledge relationships and metacognitive assessment. "
"Use remember only for durable useful knowledge, not every utterance. Prefer hypothesis unless "
"evidence justifies confirmed. Use checkpoint after meaningful progress and goal_add for multi-step "
"work. Use goal_update for objective lifecycle, depend for cycle-safe prerequisites, index for "
"optional semantic indexing, and consolidate only confirmed memories with evidence. Search before "
"repeating known procedures. Use reflect to assess complex requests. Use consult_local to obtain an "
"independent local-model opinion through Ollama when configured, then critically review its response. "
"New memories are conservatively checked for related-topic links. Use graph_status to inspect the knowledge graph, graph_sync to refresh Obsidian, and obsidian_export to generate Markdown views; SQLite remains authoritative."),
"tier":"core","brief":"Stores and retrieves memories, validates evidence, and tracks objectives/checkpoints.",
"parameters":{"type":"OBJECT","properties":{
"action":{"type":"STRING","enum":["status","remember","search","validate","goal_add","goal_update","goal_list","checkpoint","depend","index","consolidate","relate","graph_sync","graph_status","reflect","obsidian_export"]},
"content":{"type":"STRING"},"level":{"type":"STRING","enum":["working","episodic","semantic","consolidated"]},
"source":{"type":"STRING"},"state":{"type":"STRING","enum":["confirmed","hypothesis","stale","contested","planned","active","blocked","completed","cancelled","in_progress"]},"evidence":{"type":"STRING"},
"query":{"type":"STRING"},"memory_id":{"type":"INTEGER"},"title":{"type":"STRING"},
"description":{"type":"STRING"},"priority":{"type":"INTEGER"},"goal_id":{"type":"INTEGER"},"depends_on_goal_id":{"type":"INTEGER"},
"summary":{"type":"STRING"},"source_id":{"type":"INTEGER"},"target_id":{"type":"INTEGER"},
"relation":{"type":"STRING"},"next_step":{"type":"STRING"},"request":{"type":"STRING"},"vault_path":{"type":"STRING"}},
"required":["action"]},"handler":yon_brain}
