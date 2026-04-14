"""
streamlit_app.py

A professional web front-end for the Fraud Reasoning Engine.
Supports multi-conversation history, persistent investigative sessions, 
and professional PowerPoint deck downloads.
"""

import streamlit as st
import os
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv
import google.auth
import google.auth.transport.requests
from google.oauth2 import id_token

load_dotenv()

# ---------------------------------------------------------------------------
# Auth Helper
# ---------------------------------------------------------------------------

def get_auth_headers(target_url: str):
    """Generates an ID token for authenticating with Cloud Run."""
    # Only attempt auth if we are pointing to a cloud run service
    if ".run.app" not in target_url:
        return {}
    
    try:
        # Attempt standard OIDC token fetch (Works on GCP or with local SA Key)
        auth_req = google.auth.transport.requests.Request()
        token = id_token.fetch_id_token(auth_req, target_url)
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        # Quietly fail. If the service is --allow-unauthenticated, this is expected.
        return {}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = os.environ.get("API_URL", "http://0.0.0.0:8080").rstrip("/")
API_CHAT_URL = f"{API_BASE_URL}/chat"
API_CONVO_URL = f"{API_BASE_URL}/conversations"
API_HISTORY_URL = f"{API_BASE_URL}/history"

# Safety Shield: Initialize basic session state attributes to prevent AttributeErrors
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

st.set_page_config(
    page_title="Fraud Reasoning Engine",
    page_icon="🛡️",
    layout="wide",
)

# Custom CSS for a more premium look
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stChatMessage {
        border-radius: 15px;
        margin-bottom: 10px;
    }
    .stDownloadButton button {
        width: 100%;
        background-color: #007bff;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def start_new_investigation():
    try:
        headers = get_auth_headers(API_BASE_URL)
        response = requests.post(API_CONVO_URL, headers=headers)
        if response.status_code == 200:
            st.session_state.conversation_id = response.json()["conversation_id"]
            st.session_state.messages = []
    except Exception as e:
        st.error(f"Failed to start new investigation: {e}")


# ---------------------------------------------------------------------------
# Main Chat Area
# ---------------------------------------------------------------------------

# Always show the main title and case ID
st.title("Fraud Reasoning Engine")
if st.session_state.get("conversation_id"):
    st.caption(f"Active Investigation: `{st.session_state.conversation_id}`")

# ---------------------------------------------------------------------------
# Render Hero Screen OR Chat History
# ---------------------------------------------------------------------------

if not st.session_state.get("conversation_id"):
    # Show Hero Onboarding as the "Empty State" for a new investigation
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([0.1, 0.8, 0.1])
    with col2:
        with st.container(border=True):
            st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=60)
            st.subheader("Autonomous Investigative Intelligence")
            st.write("""
                Welcome to the **Fraud Reasoning Engine**. This workspace is ready for analysis. 
                You can query transaction data, generate risk profiles, and archive evidence.
            """)
            st.write("<br>", unsafe_allow_html=True)
            if st.button("🚀 Start New Investigation", use_container_width=True, type="primary"):
                start_new_investigation()
                st.rerun()
else:
    if not st.session_state.get("messages"):
        st.info("📊 **Suggested first steps:**\n- 'Show me fraud transactions in the last 7 days'\n- 'Which merchants have the highest risk scores?'\n- 'Analyze transactions by currency and create a report'")

    # Render active chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            # Add Subtle Timestamp for Audit Trail
            ts = msg.get("created_at")
            if ts:
                # Format as Full Audit Timestamp (e.g. 2026-04-12 14:30Z)
                if hasattr(ts, "strftime"):
                    ts_str = ts.strftime("%Y-%m-%d %H:%MZ")
                else:
                    # Robust fallback for string dates (YYYY-MM-DDTHH:MM:SS...)
                    # Converts '2026-04-12T13:08:33Z' -> '2026-04-12 13:08Z'
                    ts_str = str(ts)[:10] + " " + str(ts)[11:16] + "Z"
                st.caption(f"🕒 {ts_str}")
                
            st.markdown(msg["content"])
            
            # Display Charts
            if msg.get("charts_base64"):
                cols = st.columns(len(msg["charts_base64"]))
                for i, chart_b64 in enumerate(msg["charts_base64"]):
                    image_data = base64.b64decode(chart_b64)
                    cols[i].image(image_data)
            
            # Display Deck Download Buttons
            if msg.get("decks_base64"):
                for deck in msg["decks_base64"]:
                    deck_data = base64.b64decode(deck["base64"])
                    st.download_button(
                        label=f"📥 Download Presentation: {deck['filename']}",
                        data=deck_data,
                        file_name=deck["filename"],
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )

# ---------------------------------------------------------------------------
# Chat Execution
# ---------------------------------------------------------------------------

if st.session_state.get("conversation_id"):
    if prompt := st.chat_input("Ask about suspicious activity..."):
        
        # 1. Display user message immediately
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # 2. Invoke the Backend API
        with st.chat_message("assistant"):
            with st.spinner("Analyzing case data..."):
                try:
                    payload = {
                        "conversation_id": st.session_state.conversation_id,
                        "messages": st.session_state.messages,
                        "prompt": prompt
                    }
                    
                    response = requests.post(API_CHAT_URL, json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        answer = data.get("response", "")
                        charts_base64 = data.get("charts_base64", [])
                        decks_base64 = data.get("decks_base64", [])
                        
                        st.markdown(answer)
                        
                        # Handle Visualizations
                        if charts_base64:
                            cols = st.columns(len(charts_base64))
                            for i, chart_b64 in enumerate(charts_base64):
                                image_data = base64.b64decode(chart_b64)
                                cols[i].image(image_data)
                        
                        # Handle Decks
                        if decks_base64:
                            for deck in decks_base64:
                                deck_data = base64.b64decode(deck["base64"])
                                st.download_button(
                                    label=f"📥 Download Presentation: {deck['filename']}",
                                    data=deck_data,
                                    file_name=deck["filename"],
                                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                                )
                            
                        # State update (will be synced from DB on next load, but update locally for reactivity)
                        st.session_state.messages.append({"role": "user", "content": prompt})
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": answer, 
                            "charts_base64": charts_base64,
                            "decks_base64": decks_base64
                        })
                        
                    else:
                        st.error(f"Backend Error [{response.status_code}]: {response.text}")
                        
                except Exception as e:
                    st.error(f"Connection Error: {e}")
