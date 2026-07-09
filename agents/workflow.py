from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from agents.nodes.abnormal_check_node import abnormal_check_node
from agents.nodes.intent_node import intent_node
from agents.nodes.logistics_query_node import logistics_query_node
from agents.nodes.order_extract_node import order_extract_node
from agents.nodes.order_query_node import order_query_node
from agents.nodes.policy_retrieval_node import policy_retrieval_node
from agents.nodes.reply_generate_node import reply_generate_node
from agents.nodes.ticket_create_node import ticket_create_node
from agents.state import CopilotState
from schemas.copilot import CopilotAnalyzeRequest


WorkflowNode = Callable[[Session, CopilotState], CopilotState]


WORKFLOW_NODES: tuple[WorkflowNode, ...] = (
    intent_node,
    order_extract_node,
    order_query_node,
    logistics_query_node,
    abnormal_check_node,
    policy_retrieval_node,
    reply_generate_node,
    ticket_create_node,
)


class CopilotGraphApp:
    def __init__(self, compiled_graph: Any) -> None:
        self.compiled_graph = compiled_graph

    def invoke(self, state: CopilotState) -> CopilotState:
        result = self.compiled_graph.invoke(state)
        if isinstance(result, CopilotState):
            return result
        return CopilotState(**dict(result))


def make_langgraph_node(node: WorkflowNode) -> Callable[[CopilotState], CopilotState]:
    def wrapped(state: CopilotState) -> CopilotState:
        if state.db is None:
            raise RuntimeError("CopilotState.db is required to execute workflow nodes")
        return node(state.db, state)

    wrapped.__name__ = node.__name__
    return wrapped

def build_copilot_graph() -> CopilotGraphApp:
    graph = StateGraph(CopilotState)
    node_names: list[str] = []

    for node in WORKFLOW_NODES:
        node_name = node.__name__
        node_names.append(node_name)
        graph.add_node(node_name, make_langgraph_node(node))

    graph.add_edge(START, node_names[0])
    for current_node, next_node in zip(node_names, node_names[1:]):
        graph.add_edge(current_node, next_node)
    graph.add_edge(node_names[-1], END)
    return CopilotGraphApp(graph.compile())


def run_copilot_workflow(
    *,
    db: Session,
    payload: CopilotAnalyzeRequest,
    run_id: str,
) -> CopilotState:
    graph = build_copilot_graph()
    return graph.invoke(CopilotState(payload=payload, run_id=run_id, db=db))
