# SheetAgent Execution Flow

This document outlines the execution flow of the SheetAgent, from receiving an API request to returning the final analysis file.

## 1. API Endpoint (`POST /opos/analyze`)

- **File:** `app/api/endpoints/opos.py`
- The process starts when a POST request containing a JSON body with a `workbook_url` is sent to the `/opos/analyze` endpoint.
- This endpoint is responsible for receiving the request and calling the `run_analysis` function, which handles the core logic.

## 2. Analysis Service (`run_analysis`)

- **File:** `app/services/analysis_service.py`
- This function orchestrates the entire analysis workflow.
- It begins by creating a secure, temporary directory. This ensures that all file operations are isolated and cleaned up automatically after the process is complete.
- It then calls `load_problem` to download the user's workbook and prepare the data for analysis.

## 3. Data Loading (`load_problem`)

- **File:** `app/dataset/dataloader.py`
- This function handles the initial data setup.
- It downloads the Excel workbook from the `workbook_url` provided in the request.
- It reads each sheet from the workbook using `pandas` and converts it into a table in a new SQLite database file. This allows the agent to query the data using standard SQL.
- A `SheetProblem` object is returned, containing the path to the workbook, the path to the SQLite database, the user's instructions (prompt), and a list of sheet names.

## 4. Session Initialization (`Session` class)

- **File:** `app/core/session.py`
- Back in the `run_analysis` function, a `Sandbox` instance is created. This provides a secure, isolated environment where the agent can execute code without accessing the host system's file system or network.
- A `Session` object is then initialized. This class is the heart of the agent's operation and sets up several key components:
    - **Tools:**
        - `PythonInterpreter`: A powerful tool that allows the agent to execute Python code within the `Sandbox`. This is used for all data manipulation, analysis, and visualization tasks.
        - `SheetSelector`: A tool that allows the agent to inspect the schema of the tables (i.e., the sheets) in the SQLite database.
        - `AnswerSubmitter`: A tool for the agent to submit its final answer.
    - **Planner:** An LLM-based agent (e.g., GPT-4) that acts as the "brain" of the operation. It is initialized with a detailed system prompt that includes the user's instructions, the database schema, and a description of the available tools.

## 5. Iterative Execution (`Session.run`)

- **File:** `app/core/session.py`
- The `Session.run()` method kicks off an iterative loop where the agent works to solve the user's request. This process can be described as a "thought-action-observation" cycle:
    1.  **Thought:** The `Planner` analyzes the current state and the user's instructions and decides on the next step to take.
    2.  **Action:** The `Planner` chooses a tool to use and generates the necessary input for it. Most frequently, this is the `Python Interpreter` tool, for which the `Planner` generates a block of Python code to execute.
    3.  **Observation:** The chosen tool is executed with the provided input. The `PythonInterpreter` runs the code in the `Sandbox`, and the output (e.g., the result of a `print()` statement, a DataFrame, or an error message) is captured. This output becomes the "observation."
- The observation is then fed back to the `Planner` in the next iteration, informing its next thought and action.
- This loop continues until the `Planner` determines that it has completed the analysis and fulfilled all the user's instructions.

## 6. Output and Cleanup

- **File:** `app/services/analysis_service.py`
- Once the `Session.run()` method completes, the `run_analysis` function takes over again.
- The final output of the analysis is an Excel file named `workbook_new.xlsx`, which is saved in the session's specific output directory within the main temporary directory.
- This output file is then uploaded to a pre-configured Google Cloud Storage (GCS) bucket.
- The public URL for the newly uploaded file in GCS is generated.
- This URL is returned in the JSON response to the original API request.
- Finally, the temporary directory and all its contents (including the original workbook, the SQLite database, and any intermediate files) are automatically and securely deleted. 