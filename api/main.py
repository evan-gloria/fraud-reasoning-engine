from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import base64
import re
from pathlib import Path

import os
from reasoning_engine.fraud_investigator import get_agent, ask_agent
from api.history_manager import HistoryManager
from agent_skills.storage_skill import upload_chart_to_gcs

app = FastAPI(title="Fraud Reasoning Engine Backend")
history_manager = HistoryManager()
ARTIFACT_BUCKET = os.environ.get("GCP_ARTIFACT_BUCKET")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Fraud Reasoning Engine Backend",
        "documentation": "/docs"
    }

@app.get("/audit/firestore")
def audit_firestore():
    """Diagnostic endpoint to verify database visibility."""
    return history_manager.get_collection_counts()

# ---------------------------------------------------------------------------
# History Endpoints
# ---------------------------------------------------------------------------

@app.get("/conversations")
def list_conversations():
    print("🕵️ [API Trace] Fetching Case Registry from memory...")
    convos = history_manager.get_conversations()
    print(f"🕵️ [API Trace] Found {len(convos)} total cases in registry.")
    return convos

@app.post("/conversations")
def create_conversation():
    convo_id = history_manager.create_conversation()
    return {"conversation_id": convo_id}

@app.get("/history/{conversation_id}")
def get_history(conversation_id: str):
    return history_manager.get_history(conversation_id)

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    history_manager.delete_conversation(conversation_id)
    return {"status": "deleted"}

class RenameRequest(BaseModel):
    title: str

@app.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, request: RenameRequest):
    history_manager.rename_conversation(conversation_id, request.title)
    return {"status": "renamed"}

# ---------------------------------------------------------------------------
# Chat Endpoints
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str
    charts_base64: Optional[List[str]] = None
    decks_base64: Optional[List[Dict[str, str]]] = None # List of {"filename": "...", "base64": "..."}

class ChatRequest(BaseModel):
    conversation_id: str
    messages: List[Message]
    prompt: str

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    try:
        # 1. Save User Message to DB
        history_manager.save_message(
            conversation_id=request.conversation_id,
            role="user",
            content=request.prompt
        )

        # 2. Rebuild history for Gemini from Pydantic models
        history = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # 3. Initialize Vertex Session & Query Agent
        agent = get_agent(history_dicts=history)
        result = ask_agent(chat_session=agent, user_input=request.prompt)
        answer = result["answer"]
        sql_query = result["sql_query"]
        
        # 4. Extract & Archive Assets (Charts/Decks)
        charts_base64 = []
        decks_base64 = []
        gcs_uris = []
        
        # 4a. Process Charts
        chart_matches = re.findall(r'<CHART>(.*?)</CHART>', answer)
        for chart_filename in chart_matches:
            full_tag = f"<CHART>{chart_filename}</CHART>"
            answer = answer.replace(full_tag, "").strip()
            chart_path = Path(__file__).parent.parent / "ui" / "static" / chart_filename.strip()
            if chart_path.exists():
                # Encode for UI
                with open(chart_path, "rb") as image_file:
                    charts_base64.append(base64.b64encode(image_file.read()).decode('utf-8'))
                
                # Archive to GCS with Metadata if bucket configured
                if ARTIFACT_BUCKET:
                    try:
                        gs_uri = upload_chart_to_gcs(
                            local_file_path=str(chart_path),
                            bucket_name=ARTIFACT_BUCKET,
                            transaction_id=request.conversation_id, # Using Convo ID as case ref
                            user_prompt=request.prompt,
                            sql_query=sql_query or "N/A"
                        )
                        gcs_uris.append(gs_uri)
                    except Exception as e:
                        print(f"⚠️ [Archival Error] Failed to upload chart: {e}")

        # 4b. Process Decks
        deck_matches = re.findall(r'<DECK>(.*?)</DECK>', answer)
        for deck_filename in deck_matches:
            full_tag = f"<DECK>{deck_filename}</DECK>"
            answer = answer.replace(full_tag, "").strip()
            deck_path = Path(__file__).parent.parent / "ui" / "static" / "decks" / deck_filename.strip()
            if deck_path.exists():
                # Encode for UI
                with open(deck_path, "rb") as deck_file:
                    decks_base64.append({
                        "filename": deck_filename.strip(),
                        "base64": base64.b64encode(deck_file.read()).decode('utf-8')
                    })
                
                # Archive to GCS with Metadata if bucket configured
                if ARTIFACT_BUCKET:
                    try:
                        gs_uri = upload_chart_to_gcs(
                            local_file_path=str(deck_path),
                            bucket_name=ARTIFACT_BUCKET,
                            transaction_id=request.conversation_id,
                            user_prompt=request.prompt,
                            sql_query=sql_query or "Presentation Summary"
                        )
                        gcs_uris.append(gs_uri)
                    except Exception as e:
                        print(f"⚠️ [Archival Error] Failed to upload deck: {e}")
        
        # 5. Save AI Response to DB
        history_manager.save_message(
            conversation_id=request.conversation_id,
            role="assistant",
            content=answer,
            charts_base64=charts_base64,
            decks_base64=decks_base64,
            gcs_uris=gcs_uris
        )
                    
        return {
            "response": answer,
            "charts_base64": charts_base64,
            "decks_base64": decks_base64,
            "sql_query": sql_query,
            "gcs_uris": gcs_uris
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
