"""
streamlit_app.py

A professional web front-end for the Fraud Reasoning Engine.
Built using Streamlit to provide a sleek, chat-based interface.
It is completely decoupled and communicates with the Backend via REST API.
"""

import streamlit as st
import os
import requests
import base64

# Note: We do NOT load internal environment variables like GCP_PROJECT here!
# This UI is purely a presentation layer. It only needs the API_URL.
API_URL = os.environ.get("API_URL", "http://0.0.0.0:8080/chat")

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
    and summarizes the findings safely behind our decoupled REST API.
    """
)

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
        
        # Display past charts dynamically
        if msg.get("charts_base64"):
            for chart_b64 in msg["charts_base64"]:
                image_data = base64.b64decode(chart_b64)
                st.image(image_data)

# ---------------------------------------------------------------------------
# Chat execution
# ---------------------------------------------------------------------------

if prompt := st.chat_input("E.g., How many transactions were flagged as fraud?"):
    
    # 1. Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # 2. Invoke the Decoupled Backend API
    with st.chat_message("assistant"):
        with st.spinner("Investigating remotely..."):
            try:
                # Prepare payload
                payload = {
                    "messages": st.session_state.messages,
                    "prompt": prompt
                }
                
                response = requests.post(API_URL, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("response", "")
                    charts_base64 = data.get("charts_base64", [])
                    
                    st.markdown(answer)
                    
                    # Package state objects
                    msg_state = {"role": "assistant", "content": answer, "charts_base64": charts_base64}
                    
                    if charts_base64:
                        for chart_b64 in charts_base64:
                            image_data = base64.b64decode(chart_b64)
                            st.image(image_data)
                        
                    # Commit to history state
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    st.session_state.messages.append(msg_state)
                    
                else:
                    st.error(f"Backend API Error [{response.status_code}]: {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error(f"Failed to connect to Backend Server at `{API_URL}`. Ensure FastAPI is running!")
            except Exception as e:
                st.error(f"Unhandled Streamlit Error: {str(e)}")
