"""
streamlit_app.py

A professional web front-end for the Fraud Reasoning Engine.
Built using Streamlit to provide a sleek, chat-based interface.
"""

import streamlit as st
import sys
from pathlib import Path

# Provide access to our agent and skills folders
sys.path.append(str(Path(__file__).parent.parent))

from reasoning_engine.fraud_investigator import get_agent, SYSTEM_INSTRUCTION

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Fraud Reasoning Engine",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title("🛡️ Fraud Reasoning Engine")
st.markdown(
    """
    **Ask natural language questions about your BigQuery credit card transactions.** 
    The Vertex AI agent automatically translates your questions into SQL, runs the queries, 
    and summarizes the findings. 
    """
)

# ---------------------------------------------------------------------------
# Agent Initialization
# ---------------------------------------------------------------------------

def load_agent():
    """
    Loads the Langchain Vertex Agent and returns it.
    """
    return get_agent()

try:
    if "agent" not in st.session_state:
        st.session_state.agent = load_agent()
    agent = st.session_state.agent
except Exception as e:
    st.error(f"Failed to load Vertex AI Agent: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Chat State Management
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I am your Senior Corporate Fraud Investigator. What data would you like me to pull?"}
    ]

# Render existing chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Display past charts if they exist in state
        if msg.get("chart"):
            chart_path = Path(__file__).parent / "static" / msg["chart"]
            if chart_path.exists():
                st.image(str(chart_path))

# ---------------------------------------------------------------------------
# Chat execution
# ---------------------------------------------------------------------------

if prompt := st.chat_input("E.g., How many transactions were flagged as fraud?"):
    
    # 1. Display and save user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # 2. Invoke the agent
    with st.chat_message("assistant"):
        with st.spinner("Investigating..."):
            import re
            from pathlib import Path
            try:
                from reasoning_engine.fraud_investigator import ask_agent
                
                # Query the native Vertex AI chat session and automatically trigger tool calling
                answer = ask_agent(chat_session=agent, user_input=prompt)
                
                # Intercept any graph tags intended for Streamlit rendering
                chart_match = re.search(r'<CHART>(.*?)</CHART>', answer)
                chart_filename = None
                if chart_match:
                    chart_filename = chart_match.group(1).strip()
                    # Strip the hidden tag from the underlying text so the user doesn't see it
                    answer = answer.replace(chart_match.group(0), "")
                
                # Display output text
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer, "chart": chart_filename})
                
                # If the agent drew a chart, load it from the static folder and display it!
                if chart_filename:
                    chart_path = Path(__file__).parent / "static" / chart_filename
                    if chart_path.exists():
                        st.image(str(chart_path))
                    else:
                        st.warning(f"Could not load image: {chart_path}")
                
            except Exception as e:
                error_msg = f"Sorry, I encountered an error during my investigation: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
