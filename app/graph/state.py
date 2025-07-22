from typing import TypedDict, Annotated, List, Optional
from pathlib import Path

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langgraph.graph import add_messages

from app.dataset.dataloader import SheetProblem
from app.core.sandbox import Sandbox
from app.core.prompt_manager import PromptManager

class GraphState(TypedDict):
    """
    State representation for the LangGraph workflow.
    
    This class represents the state that is passed between nodes in the graph.
    It contains all the necessary information for the workflow to execute.
    """
    # Static components that don't change during execution
    problem: SheetProblem
    sandbox: Sandbox
    planner_chain: Runnable
    max_steps: int
    output_dir: Path
    prompt_manager: PromptManager
    
    # Dynamic components that are updated during execution
    # IMPORTANT: add_messages is used to automatically add the messages to the state 
    messages: Annotated[List[BaseMessage], add_messages]
    current_sheet_state: str
    previous_sheet_state: str
    step: int
