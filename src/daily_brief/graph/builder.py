from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from daily_brief.graph.context import WorkflowDependencies
from daily_brief.graph.nodes import MorningBriefNodes
from daily_brief.graph.state import MorningBriefState


def build_morning_brief_graph(dependencies: WorkflowDependencies) -> Any:
    nodes = MorningBriefNodes(dependencies)
    graph = StateGraph(MorningBriefState)

    graph.add_node("ingest_sources", nodes.ingest_sources)
    graph.add_node("clean_and_dedup", nodes.clean_and_dedup)
    graph.add_node("lightweight_rank", nodes.lightweight_rank)
    graph.add_node("llm_evaluate_items", nodes.llm_evaluate_items)
    graph.add_node("select_items", nodes.select_items)
    graph.add_node("relax_selection", nodes.relax_selection)
    graph.add_node("plan_brief", nodes.plan_brief)
    graph.add_node("summarize_sections", nodes.summarize_sections)
    graph.add_node("render_markdown", nodes.render_markdown)
    graph.add_node("deliver_output", nodes.deliver_output)
    graph.add_node("persist_artifacts", nodes.persist_artifacts)

    graph.add_edge(START, "ingest_sources")
    graph.add_edge("ingest_sources", "clean_and_dedup")
    graph.add_edge("clean_and_dedup", "lightweight_rank")
    graph.add_edge("lightweight_rank", "llm_evaluate_items")
    graph.add_edge("llm_evaluate_items", "select_items")
    # If the first-pass editorial threshold is too strict, route through a
    # fallback node that relaxes inclusion criteria before planning the brief.
    graph.add_conditional_edges(
        "select_items",
        nodes.route_after_selection,
        {"relax_selection": "relax_selection", "plan_brief": "plan_brief"},
    )
    graph.add_edge("relax_selection", "plan_brief")
    graph.add_edge("plan_brief", "summarize_sections")
    graph.add_edge("summarize_sections", "render_markdown")
    graph.add_edge("render_markdown", "deliver_output")
    graph.add_edge("deliver_output", "persist_artifacts")
    graph.add_edge("persist_artifacts", END)

    return graph.compile(checkpointer=dependencies.checkpointer)


def workflow_mermaid() -> str:
    return """flowchart TD
    START([START]) --> ingest_sources
    ingest_sources --> clean_and_dedup
    clean_and_dedup --> lightweight_rank
    lightweight_rank --> llm_evaluate_items
    llm_evaluate_items --> select_items
    select_items -->|enough items| plan_brief
    select_items -->|too few items| relax_selection
    relax_selection --> plan_brief
    plan_brief --> summarize_sections
    summarize_sections --> render_markdown
    render_markdown --> deliver_output
    deliver_output --> persist_artifacts
    persist_artifacts --> END([END])
"""
