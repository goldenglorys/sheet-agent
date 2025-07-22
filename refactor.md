# LangGraph Refactoring Plan

This document outlines the plan to refactor the agent orchestration logic from the current `Session` class to a `langgraph` `StateGraph`.

## 1. Core Concepts

The new architecture will be built around a `StateGraph`, a state machine that orchestrates the flow of the analysis.

-   **State:** A Pydantic model (`GraphState`) will represent the state of the workflow. It will hold all the necessary information that needs to be passed between the different steps of the analysis, such as the user's instructions, the current workbook state, agent thoughts, and tool outputs.
-   **Nodes:** Each step in the current `Session.run` loop will be refactored into a node in the graph. These nodes are functions that take the current state as input, perform a specific task, and return an updated state.
-   **Edges:** Conditional edges will control the flow of the graph, directing the workflow based on the output of each node. For example, after the `Planner` node runs, an edge will decide whether to execute a tool, ask the `Informer` for more information, or finish the analysis.

## 2. Graph State (`GraphState`)

The state will be managed using a `TypedDict` with `Annotated` fields to control how state is updated.

```python
class GraphState(TypedDict):
    problem: SheetProblem
    sandbox: Sandbox
    planner: Planner
    informer: Optional[Informer]
    tools: Dict[str, BaseTool]
    max_steps: int
    
    # Fields that will be updated during the run
    messages: Annotated[List[BaseMessage], add_messages]
    step: int
```

## 3. Graph Nodes

The core logic of the current `Session` class will be broken down into the following nodes:

1.  **`planner_node`:**
    -   This node will encapsulate the logic of calling the `Planner` agent.
    -   It will take the current `messages` from the state, send them to the `Planner`, and get back a response containing the agent's thoughts and a proposed action.
    -   The response from the `Planner` will be added back to the `messages` list in the state.

2.  **`tool_node`:**
    -   This node will be responsible for executing the action proposed by the `Planner`.
    -   It will parse the action and its input from the `Planner`'s last message.
    -   It will then call the corresponding tool (e.g., `PythonInterpreter`) and execute it in the `Sandbox`.
    -   The output of the tool (the "observation") will be added to the `messages` list as a `ToolMessage`.

3.  **`informer_node` (Optional):**
    -   If the `with_informer` flag is enabled, this node will be called.
    -   It will call the `Informer` agent to get additional context or "key information" that might be helpful for the `Planner`.
    -   The `Informer`'s output will be added to the state to be used in the `Planner`'s prompt.

## 4. Graph Edges and Control Flow

The control flow will be managed by conditional edges that check the state after each node's execution.

1.  **Entry Point:** The graph will start at the `planner_node`.
2.  **From `planner_node`:**
    -   After the `planner_node` runs, a conditional edge (`should_continue`) will examine the last message from the planner.
    -   If the message contains a tool call, the edge will direct the flow to the `tool_node`.
    -   If the message indicates that the task is finished ("Done" or "Finish"), the edge will direct the flow to the `END` of the graph.
3.  **From `tool_node`:**
    -   After the `tool_node` executes, the graph will always loop back to the `planner_node` to continue the analysis with the new information (the tool's observation).
4.  **Step Limit:** The `should_continue` function will also check if the number of steps has exceeded `max_steps`. If it has, the graph will terminate.

## 5. Integration with `analysis_service.py`

-   The `run_analysis` function in `app/services/analysis_service.py` will be refactored.
-   Instead of creating a `Session` object, it will initialize the `GraphState` with all the required objects (`SheetProblem`, `Sandbox`, `Planner`, `Informer`, tools).
-   It will then construct the `StateGraph`, add the nodes and edges as defined above, and compile it into a `Runnable`.
-   The analysis will be executed by calling the `graph.invoke()` method with the initial state.
-   The `Session` class (`app/core/session.py`) will be deprecated and eventually removed.

This new `langgraph`-based architecture will provide a more modular, explicit, and maintainable way to orchestrate the agent's workflow, making it easier to understand, info, and extend in the future. 