"""
Prompt manager module for SheetAgent.

This module provides a centralized class for managing prompt templates for the planner model.
It loads system prompts and few-shot examples from the prompt directory.
"""
import json
import os
from typing import Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class PromptManager:
    """
    A class that centralizes the management of prompt templates for different model types.
    
    This class contains all prompt string constants and methods for loading few-shot examples
    and creating prompt templates for planner model.
    """
    
    # System prompts that were previously in PlannerPrompt and InformerPrompt classes
    PLANNER_SYSTEM_PROMPT = """
You are a spreadsheet agent and a python expert who can find proper functions to solve complicated spreadsheet-related tasks based on language instructions.

# Prerequisites:
1. You will always receive the most up to date sheet state as 'Sheet State', which includes the headers (along with data type) and row numbers of the spreadsheet for your reference.
2. Always choose your next step based on the current sheet state.
3. Output your thoughts on how to solve the task in a <scratchpad> tag. Close the <scratchpad> tag when you have finished your thoughts.
4. Only call one tool at a time.
5. On every step, make sure to evaluate whether you have completed the task. If you have completed the task, output "Done" and end the workflow.
6. You will receive the most up to date sheet state after every tool call. Always work with the most up to date sheet state.
7. If you read a cell range, read a maximum of 10 rows and 10 columns at a time.

# Rules for writing python code:
1. The code runs in a secure sandbox. All previously written code will be appended to the code you write.
1. Only write one python code snippet per tool call.
2. The openpyxl library has already been imported as `openpyxl`. You do not need to import it again.
3. ONLY use openpyxl for manipulating spreadsheets.
4. Do not write comments unless you would cry without them. If you write a comment, make it concise.
5. The workbook is already loaded in the sandbox and can be accessed as `workbook`. DO NOT CREATE A NEW WORKBOOK.
6. If you want to read the output of the code or some value, use the `print()` function. For example, if you want to read the output of a dataframe, use `print(df.head())`.
7. If an error occurs, do not panic. Read the error message and try to fix the error. If you cannot fix the error, output the error message and end the workflow.
"""

    OBSERVATION_PROMPT = """
The sheet state has been updated by your previous tool call. 
---------
Sheet state: 
{sheet_state}
"""
    # User initial prompt templates
    USER_INIT_PROMPT = """
Context: 
{context}

---

Sheet state: 
{sheet_state}

---

Task List:
{instruction}
"""

    def __init__(self):
        """
        Initialize the PromptManager.
        """
        # Get the current path of the prompt directory
        self.prompt_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompt")

    def get_observation_prompt(self, sheet_state: str) -> SystemMessage:
        """
        Get the observation prompt for the planner model.
        """
        return SystemMessage(content=self.OBSERVATION_PROMPT.format(sheet_state=sheet_state))
    
    def get_planner_prompt_template(self) -> ChatPromptTemplate:
        """
        Create a prompt template for the planner model using MessagesPlaceholder.
            
        Returns:
            A ChatPromptTemplate containing the system prompt and MessagesPlaceholder.
        """
        # Get system prompt based on model type
        system_content = self._get_system_prompt()
        # Get the current path of the prompt directory
        prompt_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompt") 
        
        # few_shot_examples = PromptManager._load_few_shot_examples(prompt_dir)
                    
        # Create the prompt template with MessagesPlaceholder
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_content),
            # *few_shot_examples,
            MessagesPlaceholder(variable_name="messages")
        ])
        
        return prompt_template
    
    def format_initial_user_message(
        self, 
        context: str, 
        sheet_state: str, 
        instruction: str, 
    ) -> HumanMessage:
        """
        Format the initial user message using the appropriate template.
        
        Args:
            context: The context for the task.
            sheet_state: The current state of the sheet.
            instruction: The task instruction.
            
        Returns:
            A HumanMessage with the formatted content.
        """
        content = self.USER_INIT_PROMPT.format(
                context=context if context else "",
                sheet_state=sheet_state,
                instruction=instruction
            )
        
        return HumanMessage(content=content)
    
    @staticmethod
    def _get_system_prompt() -> str:
        """
        Get the system prompt for the planner model.
        
        Returns:
            The system prompt as a string.
        """
        return PromptManager.PLANNER_SYSTEM_PROMPT

    @staticmethod
    def _load_few_shot_examples(prompt_dir: str) -> List[BaseMessage]:
        """
        Load few-shot examples for the specified model type and parse them into a list of BaseMessage.
        
        Args:
            prompt_dir: The directory path where the prompt files are located.
        
        Returns:
            A list of BaseMessage.
        """

        # Read the JSONL file
        jsonl_path = os.path.join(prompt_dir, "planner.jsonl")
        with open(jsonl_path, "r") as f:
            examples = list(f)

        # Parse the few-shot examples
        few_shot = []
        for example in examples:
            chats = json.loads(example)
            shot = chats[1:]  # Skip the system message, which is handled separately
            few_shot.append(shot)

        # Parse the few-shot examples into a list of BaseMessage
        messages: List[BaseMessage] = []
        for example in few_shot:
            for i, message in enumerate(example):
                if i % 2 == 0:  # Even indices are human messages
                    messages.append(HumanMessage(content=message["content"]))
                else:  # Odd indices are AI messages
                    messages.append(AIMessage(content=message["content"]))
                    
        return messages


# Simple test function to verify the implementation
if __name__ == "__main__":
    # Create a PromptManager instance
    prompt_manager = PromptManager()
    
    # Test planner prompt template 
    planner_prompt = prompt_manager.get_planner_prompt_template()
    print("Planner prompt template created successfully")
    
    
    # Test formatting initial user message
    initial_message = prompt_manager.format_initial_user_message(
        context="Test context",
        sheet_state="Sheet A: 10 rows, 5 columns",
        instruction="Calculate the sum of column A"
    )
    print("Initial user message formatted successfully")
    
    