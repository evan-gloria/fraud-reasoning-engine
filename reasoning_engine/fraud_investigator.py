"""
fraud_investigator.py

Defines the fraud investigation agent using Vertex AI Reasoning Engines SDK.
This agent acts as a Senior Corporate Fraud Investigator and has access to
the run_text_to_sql tool to query the BigQuery database dynamically.
"""

import os
import vertexai
from dotenv import load_dotenv

# Ensure the parent directory is in path when running standalone
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agent_skills.bq_sql_skill import run_text_to_sql

load_dotenv()

GCP_PROJECT = os.environ["GCP_PROJECT"]
GCP_REGION = os.environ.get("GCP_REGION", "australia-southeast1")
GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = """
You are a Senior Corporate Fraud Investigator at a major retail bank.
Your job is to answer questions about credit card transactions and identify 
patterns of fraudulent behavior.

You have access to a tool that can execute SQL queries against the 
bank's transactional data in BigQuery.

When asked a question:
1. Translate the user's request into a question suitable for your SQL tool.
2. Call the tool to get the data.
3. Review the returned data.
4. Formulate a final, professional response summarizing the findings.

Rules:
- If the tool returns an error, tell the user you encountered a database error.
- Never guess or make up numbers. Only use the numbers returned by your tool.
- Always be professional, concise, and helpful.
- If the user asks a question entirely unrelated to banking or fraud (e.g. "Write a poem"), 
  politely decline and remind them of your role.
"""


import vertexai
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration, Part
from agent_skills.bq_sql_skill import run_text_to_sql
from agent_skills.graph_skill import generate_chart

# 1. Define the Native Vertex AI Tool for SQL
sql_func = FunctionDeclaration(
    name="run_text_to_sql",
    description="Answers natural language questions about credit card transactions using BigQuery.",
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The natural language question to translate to SQL."
            }
        },
        "required": ["question"]
    }
)

# 2. Define the Native Vertex AI Tool for Graphing
graph_func = FunctionDeclaration(
    name="generate_chart",
    description="Generates a chart image from arrays of data and returns a tag to display it.",
    parameters={
        "type": "object",
        "properties": {
            "chart_type": {"type": "string", "description": "The type of chart to draw ('bar', 'line', 'scatter', 'pie')"},
            "title": {"type": "string", "description": "Chart title"},
            "x_labels": {"type": "array", "items": {"type": "string"}, "description": "Categories for X axis"},
            "y_values": {"type": "array", "items": {"type": "number"}, "description": "Values for Y axis"}
        },
        "required": ["chart_type", "title", "x_labels", "y_values"]
    }
)

native_tools = Tool(function_declarations=[sql_func, graph_func])

def get_agent():
    """
    Initialises and returns a native Vertex AI Chat session.
    """
    print("🤖 Booting up Native Vertex AI Agent...")
    vertexai.init(project=GCP_PROJECT, location=GCP_REGION)

    model = GenerativeModel(
        GEMINI_MODEL,
        system_instruction=[SYSTEM_INSTRUCTION],
        tools=[native_tools]
    )
    
    # Return a stateful chat session
    return model.start_chat()

def ask_agent(chat_session, user_input: str) -> str:
    """
    Helper function to send a message to the native Vertex chat session
    and automatically handle any tool calling if the model requests it.
    """
    response = chat_session.send_message(user_input)
    
    if not response.candidates:
        return response.text
        
    part = response.candidates[0].content.parts[0]
    
    # Handle multiple tool calling turns if Gemini needs to do several things
    while part.function_call:
        func_name = part.function_call.name
        
        if func_name == "run_text_to_sql":
            question_arg = part.function_call.args["question"]
            print(f"\n   [Agent Tool Called] run_text_to_sql('{question_arg}')")
            tool_result = run_text_to_sql(question_arg)
            
        elif func_name == "generate_chart":
            chart_type_arg = part.function_call.args["chart_type"]
            title_arg = part.function_call.args["title"]
            x_labels_arg = list(part.function_call.args["x_labels"])
            y_values_arg = list(part.function_call.args["y_values"])
            print(f"\n   [Agent Tool Called] generate_chart('{chart_type_arg}', '{title_arg}')")
            tool_result = generate_chart(chart_type_arg, title_arg, x_labels_arg, y_values_arg)
            
        else:
            tool_result = f"Error: Unknown tool {func_name}"
            
        # Send the result back to Gemini
        response = chat_session.send_message(
            Part.from_function_response(
                name=func_name,
                response={"content": tool_result}
            )
        )
        part = response.candidates[0].content.parts[0]
            
    return response.text

if __name__ == "__main__":
    chat = get_agent()
    print("\n✅ Agent online.")
    print("Welcome to the Fraud Investigation terminal.")
    print("Type 'exit' or 'quit' to leave.\n")

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                continue
                
            print("\n   [Agent is thinking...]")
            answer = ask_agent(chat, user_input)
            print(f"Agent:\n{answer}\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")
            
    print("Logging off.")

