"""
LangGraph implementation for SheetAgent.

This module defines the GraphState model and node functions for the LangGraph workflow.
It includes LangSmith integration for tracing and monitoring.
"""
from typing import Dict, List,Any
from pathlib import Path
import logging

from langchain_core.tools import BaseTool
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langsmith import traceable

from app.utils.enumeration import MODEL_TYPE
from app.dataset.dataloader import SheetProblem
from app.core.sandbox import Sandbox
from app.graph.tools import python_executor, cell_range_reader
from app.core.prompt_manager import PromptManager
from app.utils.utils import parse_think
from app.graph.state import GraphState

# Configure logger
logger = logging.getLogger(__name__)

@traceable(name="Planner Node", run_type="chain")
def planner_node(state: GraphState) -> GraphState:
    """
    Node function for the planner agent.
    
    This function calls the planner agent with the current messages and returns
    the updated state with the planner's response added to the messages.
    
    Args:
        state: The current state of the graph.
        
    Returns:
        The updated state with the planner's response.
    """
    logger.info(f"Executing planner node at step {state['step']}")
    
    # Extract the necessary components from the state
    planner_chain = state["planner_chain"]
    messages = state["messages"]
    sheet_state_changed = state["previous_sheet_state"] != state["current_sheet_state"]
    
    # Get observation only if the sheet state has changed
    if sheet_state_changed:
        observation = state["prompt_manager"].get_observation_prompt(state["current_sheet_state"])
        
    # LLM CALL
    response = planner_chain.invoke({
        "messages": [*messages, observation] if sheet_state_changed else messages
    })
    thought = None
    if response:
        # Try to parse the thought from the planner's message if it has content
        if hasattr(response, 'content') and response.content:
            try:
                thought = parse_think(response.content)
                logger.info(f"Parsed thought: {thought[:100]}...")
            except Exception as e:
                # If parsing fails, continue without adding a thought
                logger.warning(f"Failed to parse thought from planner message: {str(e)}")
        
        return {
            **state, 
            "messages": [observation, response] if sheet_state_changed else [response],  # Use the response directly
            "step": state["step"] + 1
        }
    else:
        logger.warning("Planner returned empty message")
    
    return state

def should_end(state: GraphState):
    max_steps_reached = state["step"] >= state["max_steps"]
    return max_steps_reached

def build_graph(tools: List[BaseTool]) -> StateGraph:
    """
    Builds and returns the StateGraph for the agent workflow.
    
    This function constructs the StateGraph with the appropriate nodes and edges
    based on the refactoring plan. It defines the control flow between the nodes
    and compiles the graph into a runnable.
    
    Args:
        tools: List of tools to be used by the ToolNode.
        
    Returns:
        The compiled StateGraph.
    """
    graph = StateGraph(GraphState)
    
    graph.add_node("planner", planner_node)
    graph.add_node("tools", ToolNode(tools))
    # Always go back to planner after tools are called
    graph.add_edge("tools", "planner") 
    
    graph.add_conditional_edges(
        "planner",
        should_end,
        {
            True: END,
            False: "tools"
        }
    )

    graph.set_entry_point("planner")    
    
    graph = graph.compile()
    
    return graph

 
def create_initial_state(
    problem: SheetProblem,
    sandbox: Sandbox,
    planner: Runnable,
    output_dir: Path,
    max_steps: int = 5, # ATTENTION: This determines the maximum number of steps the agent can take.
    prompt_manager: PromptManager = None,
) -> GraphState:
    """
    Creates the initial state for the graph execution.
    
    Args:
        problem: The sheet problem to analyze.
        sandbox: The sandbox instance for secure code execution.
        planner: The planner agent.
        output_dir: The directory where output files will be saved.
        max_steps: Maximum number of steps to execute.
        prompt_manager: The PromptManager instance for formatting prompts.
        
    Returns:
        The initial state for the graph execution.
    """
    # Get the sheet state from the sandbox
    sheet_state = sandbox.get_sheet_state()
    
    # Create the initial human message with the properly formatted content
    initial_message = prompt_manager.format_initial_user_message(
        context=problem.context if problem.context else "",
        sheet_state=sheet_state,
        instruction=problem.instruction,
    )
    
    # Create the initial state
    return {
        # Static components
        "problem": problem,
        "sandbox": sandbox,
        "planner_chain": planner,
        "max_steps": max_steps,
        "output_dir": output_dir,
        "prompt_manager": prompt_manager,
        
        # Dynamic components
        "messages": [initial_message],
        "step": 0,
        "previous_sheet_state": sheet_state,
        "current_sheet_state": sheet_state
    }


class SheetAgentGraph:
    """
    A wrapper class for the StateGraph that provides a simplified interface for execution.
    
    This class encapsulates the graph construction and execution, providing a clean
    interface for the analysis service to use. It integrates with LangSmith for
    tracing and monitoring of the agent's execution.
    """
    
    def __init__(
        self,
        problem: SheetProblem,
        output_dir: Path,
        sandbox: Sandbox,
        max_steps: int = 1,
        planner_model_name: str = MODEL_TYPE.GPT_4_1106.value,
    ):
        """
        Initializes the SheetAgentGraph.
        
        Args:
            problem: The sheet problem to analyze.
            output_dir: The directory where output files will be saved.
            sandbox: The sandbox instance for secure code execution.
            max_steps: Maximum number of steps to execute.
            planner_model_name: The name of the model to use for planning.
        """
        from app.core.config import get_settings
        
        self.problem = problem
        self.output_dir = output_dir
        self.sandbox = sandbox
        self.max_steps = max_steps
        
        # Initialize the prompt manager
        self.prompt_manager = PromptManager()
        
        # Initialize the language models
        settings = get_settings()
        
        planner_model = ChatOpenAI(
            model="o4-mini-2025-04-16",
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
            # temperature=0.0,
            timeout=60
        )
        
        # Create list of tools for binding
        self.tool_list = [python_executor, cell_range_reader]
        
        # Bind tools to the planner model
        planner_model = planner_model.bind_tools(self.tool_list)
        
        # Create the planner chain using the prompt manager
        planner_prompt = self.prompt_manager.get_planner_prompt_template()
        planner_chain = planner_prompt | planner_model
        self.planner = planner_chain
        
        # Build the graph with the tool list
        self.graph = build_graph(self.tool_list)
    
    @traceable(name="SheetAgent", run_type="chain")
    def run(self) -> Dict[str, Any]:
        """
        Runs the graph with the initial state.
        
        This method is traced with LangSmith to provide monitoring and debugging
        capabilities for the agent's execution.
        
        Returns:
            The final state after graph execution.
        """
        logger.info("Starting SheetAgentGraph execution")
        
        # Initialize the workbook first before creating initial state
        logger.info("Loading workbook")
        self.sandbox.load_workbook(self.problem.workbook_path)
        
        # Create the initial state
        logger.info("Creating initial state")
        initial_state = create_initial_state(
            problem=self.problem,
            sandbox=self.sandbox,
            planner=self.planner,
            output_dir=self.output_dir,
            max_steps=self.max_steps,
            prompt_manager=self.prompt_manager,
        )
        
        # Run the graph
        logger.info("Invoking graph")
        final_state = self.graph.invoke(initial_state)
        logger.info(f"Graph execution completed after {final_state['step']} steps")
        
        # Save the final state of the workbook
        logger.info(f"Saving final workbook state to {self.output_dir}")
        self.sandbox.save(self.output_dir)
        
        return final_state 