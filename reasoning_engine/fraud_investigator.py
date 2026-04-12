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

You have access to two tools:
1. A SQL tool that executes queries against the bank's transactional data in BigQuery.
2. A charting tool that generates professional visualizations (bar, barh, line, scatter, pie, or combo charts).

When asked a question:
1. Translate the user's request into a question suitable for your SQL tool.
2. Call the tool to get the data.
3. Review the returned data.
4. Formulate a final, professional response summarizing the findings.
5. If the user asks for a chart, call the charting tool with appropriate data and descriptive axis labels.

Charting rules:
- Supported types: 'bar' (vertical), 'barh' (horizontal), 'line', 'scatter', 'pie'.
- Use 'barh' (horizontal) when you have many categories or long labels to ensure readability.
- You CAN create combo charts (bar + line in the same chart) by passing multiple series.
- You CAN set descriptive axis labels (x_label and y_label). Always use meaningful labels like "Date" or "Transaction Count", never generic labels.
- The tool automatically handles label rotation and styling for readability. Do NOT tell the user you cannot control styling.
- When scales differ significantly (e.g. daily counts vs cumulative totals), use secondary_y=true on the larger-scale series.

General rules:
- If the tool returns an error, tell the user you encountered a database error and offer to try again.
- Never guess or make up numbers. Only use the numbers returned by your tool.
- Always be professional, concise, and helpful.
- Do NOT over-explain tool limitations. Just produce the result.
- If the user asks a question entirely unrelated to banking or fraud (e.g. "Write a poem"), 
  politely decline and remind them of your role.
"""


import vertexai
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration, Part, Content
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
    description="Generates professional charts (bar, barh, line, scatter, pie, or combo) from data series. Always set descriptive x_label and y_label.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Chart title"},
            "x_labels": {"type": "array", "items": {"type": "string"}, "description": "Categories or dates for X axis (also used as slice labels for pie charts)"},
            "x_label": {"type": "string", "description": "Descriptive label for X-axis (e.g., 'Date', 'Merchant Category'). Not used for pie charts."},
            "y_label": {"type": "string", "description": "Descriptive label for primary Y-axis (e.g., 'Transaction Count', 'Amount (AUD)'). Not used for pie charts."},
            "series": {
                "type": "array",
                "description": "List of data series to plot. For pie charts, use a single series with type 'pie'.",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "Legend label for this series"},
                        "type": {"type": "string", "description": "Chart type: 'bar', 'barh', 'line', 'scatter', or 'pie'"},
                        "data": {"type": "array", "items": {"type": "number"}, "description": "Data points (values for pie slices or Y-axis values)"},
                        "secondary_y": {"type": "boolean", "description": "Set to true if this series should use a distinct right Y-axis scale (not applicable for pie)"}
                    },
                    "required": ["label", "type", "data"]
                }
            }
        },
        "required": ["title", "x_labels", "series", "x_label", "y_label"]
    }
)

native_tools = Tool(function_declarations=[sql_func, graph_func])

def get_agent(history_dicts=None):
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
    
    # Reconstruct Chat Context from REST payload
    history = []
    if history_dicts:
        for msg in history_dicts:
            role = "user" if msg["role"] == "user" else "model"
            history.append(Content(role=role, parts=[Part.from_text(msg["content"])]))
    
    # response_validation=False prevents malformed tool calls from crashing
    # the entire chat session (e.g. when the model tries to write code
    # instead of a proper structured function call)
    return model.start_chat(history=history, response_validation=False)

def ask_agent(chat_session, user_input: str) -> str:
    """
    Helper function to send a message to the native Vertex chat session
    and automatically handle any tool calling if the model requests it.
    """
    try:
        response = chat_session.send_message(user_input)
    except Exception as e:
        return f"I encountered an error processing your request. Please try rephrasing your question. (Detail: {e})"
    
    if not response.candidates:
        return response.text
        
    # Handle multiple tool calling turns if Gemini needs to do several things (including parallel calls)
    max_tool_turns = 10  # Safety limit to prevent infinite loops
    turn = 0
    while turn < max_tool_turns:
        turn += 1
        parts = response.candidates[0].content.parts
        
        # Check if the model wants to call any tools
        tool_calls = [p for p in parts if p.function_call and p.function_call.name]
        if not tool_calls:
            break
            
        tool_responses = []
        for part in tool_calls:
            func_name = part.function_call.name
            
            try:
                if func_name == "run_text_to_sql":
                    question_arg = part.function_call.args["question"]
                    print(f"\n   [Agent Tool Called] run_text_to_sql('{question_arg}')")
                    tool_result = run_text_to_sql(question_arg)
                    
                elif func_name == "generate_chart":
                    title_arg = part.function_call.args["title"]
                    x_labels_arg = list(part.function_call.args["x_labels"])
                    series_arg = list(part.function_call.args["series"])
                    x_label_arg = part.function_call.args.get("x_label", "")
                    y_label_arg = part.function_call.args.get("y_label", "")
                    print(f"\n   [Agent Tool Called] generate_chart('{title_arg}', series_count={len(series_arg)})")
                    tool_result = generate_chart(title_arg, x_labels_arg, series_arg, x_label_arg, y_label_arg)
                    
                else:
                    tool_result = f"Error: Unknown tool {func_name}"
            except Exception as e:
                print(f"   [Agent Tool Error] {func_name}: {e}")
                tool_result = f"Error executing {func_name}: {str(e)}"

            tool_responses.append(
                Part.from_function_response(
                    name=func_name,
                    response={"content": tool_result}
                )
            )
            
        # Send the batch of tool results back to Gemini in one turn
        try:
            response = chat_session.send_message(tool_responses)
        except Exception as e:
            return f"I encountered an error while processing tool results. Please try again. (Detail: {e})"
            
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

