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
if "convos" not in st.session_state:
    st.session_state.convos = []
if "reg_page" not in st.session_state:
    st.session_state.reg_page = 0

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

def fetch_investigations():
    """Explicitly pulls investigation history from the backend."""
    print("📡 [Local UI] fetch_investigations() triggered...")
    try:
        headers = get_auth_headers(API_BASE_URL)
        print(f"🔐 [Local UI] Calling {API_CONVO_URL} (Badge: {'Yes' if headers else 'No'})")
        response = requests.get(API_CONVO_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            st.session_state.convos = response.json()
            print(f"✅ [Local UI] Found {len(st.session_state.convos)} cases.")
            return True
        else:
            print(f"⚠️ [Local UI] Backend Error: {response.status_code}")
            st.session_state.convos = []
            return False
    except Exception as e:
        print(f"❌ [Local UI] Fetch Exception: {str(e)}")
        st.session_state.convos = []
        return False

# ---------------------------------------------------------------------------
# Initial Registry Load
# ---------------------------------------------------------------------------

if "convos" not in st.session_state:
    fetch_investigations()

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
            # Reactive Sync
            fetch_investigations()
    except Exception as e:
        st.error(f"Failed to start new investigation: {e}")

def load_investigation(convo_id):
    try:
        headers = get_auth_headers(API_BASE_URL)
        response = requests.get(f"{API_HISTORY_URL}/{convo_id}", headers=headers)
        if response.status_code == 200:
            st.session_state.conversation_id = convo_id
            st.session_state.messages = response.json()
    except Exception as e:
        st.error(f"Failed to load investigation: {e}")

def delete_investigation(convo_id):
    try:
        headers = get_auth_headers(API_BASE_URL)
        response = requests.delete(f"{API_CONVO_URL}/{convo_id}", headers=headers)
        if response.status_code == 200:
            if st.session_state.get("conversation_id") == convo_id:
                st.session_state.conversation_id = None
                st.session_state.messages = []
            # Reactive Sync
            fetch_investigations()
        else:
            st.error(f"Failed to delete: {response.status_code}")
    except Exception as e:
        st.error(f"Failed to delete investigation: {e}")

def rename_investigation(convo_id, new_title):
    try:
        headers = get_auth_headers(API_BASE_URL)
        response = requests.patch(f"{API_CONVO_URL}/{convo_id}", json={"title": new_title}, headers=headers)
        if response.status_code == 200:
            # Reactive Sync
            fetch_investigations()
    except Exception as e:
        st.error(f"Failed to rename investigation: {e}")

# ---------------------------------------------------------------------------
# Sidebar: Case Registry History
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🛡️ Investigator Logs")
    
    # Structural Debugging (Will help us see if data is present)
    convo_count = len(st.session_state.get("convos", []))
    if convo_count > 0:
        st.success(f"📂 {convo_count} Investigations Found")
    
    # Backend Status Overlay
    with st.expander("📡 Connectivity Status", expanded=False):
        st.success("Production Cloud Instance")
        st.caption("Fraud Investigative Engine is Online")
    
    if st.button("➕ New Investigation", use_container_width=True):
        start_new_investigation()
        st.rerun()
        
    st.divider()
    
    st.subheader("🏛️ Case Registry")
    
    # Force Refresh Button
    if st.button("🔄 Sync Case Registry", use_container_width=True, key="refresh_reg"):
        print("🔄 [Local UI] Sync Button clicked! Forcing fresh fetch...")
        if fetch_investigations():
            st.success("Registry Synced!")
        else:
            st.error("Registry Sync Failed")
        st.rerun()
    
    # 1. Registry Data Source
    convos = st.session_state.get("convos", [])

    # 2. Add a real-time Search/Filter
    search_query = st.text_input("🔍 Search Case Number or Title", "").lower()
    
    # 3. Render Registry from State with Pagination
    PAGE_SIZE = 5
    convos = st.session_state.get("convos", [])
    filtered_convos = [
        c for c in convos 
        if search_query in str(c.get('title', '')).lower() 
        or search_query in str(c.get('id', '')).lower()
    ]
    
    total_convos = len(filtered_convos)
    total_pages = (total_convos + PAGE_SIZE - 1) // PAGE_SIZE if total_convos > 0 else 1
    
    # Bound the current page if search results changed
    if st.session_state.reg_page >= total_pages:
        st.session_state.reg_page = 0
        
    start_idx = st.session_state.reg_page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_convos = filtered_convos[start_idx:end_idx]
    
    if not filtered_convos:
        if not convos:
            st.info("Central Registry is currently empty.")
        else:
            st.info("No matching cases found.")
            
    for convo in page_convos:
        is_active = st.session_state.get("conversation_id") == convo['id']
        
        item_col, edit_col, del_col = st.columns([0.6, 0.2, 0.2], gap="small")
        
        with item_col:
            prefix = "🛡️" if is_active else "📄"
            c_title = convo.get('title') or convo.get('id') or "Untitled investigation"
            label = f"{prefix} {c_title}"
            
            c_id = convo.get('id', 'Unknown_ID')
            if st.button(label, key=f"load_{c_id}", use_container_width=True, type="primary" if is_active else "secondary"):
                load_investigation(c_id)
                st.rerun()
        
        with edit_col:
            with st.popover("✏️", use_container_width=True):
                # We use a unique key and on_change callback to catch the 'Enter' key press
                new_title = st.text_input(
                    "Link to Case #", 
                    value=convo.get('title', ''), 
                    key=f"rename_input_{convo['id']}",
                    on_change=lambda id=convo['id']: rename_investigation(id, st.session_state[f"rename_input_{id}"])
                )
                if st.button("Update Registry", key=f"save_{convo['id']}", use_container_width=True):
                    rename_investigation(convo['id'], new_title)
                    st.rerun()

        with del_col:
            with st.popover("🗑️", use_container_width=True):
                st.warning("Delete this investigation? This action cannot be undone.")
                if st.button("Confirm Delete", key=f"confirm_del_{convo.get('id')}", use_container_width=True, type="primary"):
                    delete_investigation(convo.get('id', 'Unknown_ID'))
                    st.rerun()

    # 4. Pagination Controls
    if total_pages > 1:
        st.divider()
        prev_col, page_col, next_col = st.columns([0.2, 0.6, 0.2])
        with prev_col:
            if st.button("⬅️", disabled=st.session_state.reg_page == 0, use_container_width=True):
                st.session_state.reg_page -= 1
                st.rerun()
        with page_col:
            st.write(f"<p style='text-align: center; color: grey;'>Page {st.session_state.reg_page + 1} of {total_pages}</p>", unsafe_allow_html=True)
        with next_col:
            if st.button("➡️", disabled=st.session_state.reg_page >= total_pages - 1, use_container_width=True):
                st.session_state.reg_page += 1
                st.rerun()

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

if not st.session_state.get("messages"):
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
            st.info("📊 **Suggested first steps:**\n- 'Show me fraud transactions in the last 7 days'\n- 'Which merchants have the highest risk scores?'\n- 'Analyze transactions by currency and create a report'")
else:
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
