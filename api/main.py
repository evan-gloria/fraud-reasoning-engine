from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import base64
import re
from pathlib import Path

# Import our Reasoning Engine
from reasoning_engine.fraud_investigator import get_agent, ask_agent

app = FastAPI(title="Fraud Reasoning Engine Backend")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Fraud Reasoning Engine Backend",
        "documentation": "/docs"
    }

# REST API Request Schemas
class Message(BaseModel):
    role: str
    content: str
    charts_base64: Optional[List[str]] = None

class ChatRequest(BaseModel):
    messages: List[Message]
    prompt: str

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    try:
        # Convert Pydantic models to dicts to rebuild Vertex state cleanly
        history = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Initialize Vertex Session with previous network context
        agent = get_agent(history_dicts=history)
        
        # Query the Generative Agent
        answer = ask_agent(chat_session=agent, user_input=request.prompt)
        
        # Evaluate output for dynamically generated Visualizations
        charts_base64 = []
        chart_matches = re.findall(r'<CHART>(.*?)</CHART>', answer)
        
        for chart_filename in chart_matches:
            full_tag = f"<CHART>{chart_filename}</CHART>"
            answer = answer.replace(full_tag, "")
            
            # Read from the backend's local disk space and encode to Base64
            chart_path = Path(__file__).parent.parent / "ui" / "static" / chart_filename.strip()
            if chart_path.exists():
                with open(chart_path, "rb") as image_file:
                    charts_base64.append(base64.b64encode(image_file.read()).decode('utf-8'))
                    
        return {
            "response": answer,
            "charts_base64": charts_base64
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
