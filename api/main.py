from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import base64
import re
from pathlib import Path

# Import our Reasoning Engine
from reasoning_engine.fraud_investigator import get_agent, ask_agent

app = FastAPI(title="Fraud Reasoning Engine Backend")

# REST API Request Schemas
class Message(BaseModel):
    role: str
    content: str
    chart_base64: Optional[str] = None
    chart: Optional[str] = None # Legacy support

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
        chart_base64 = None
        chart_match = re.search(r'<CHART>(.*?)</CHART>', answer)
        
        if chart_match:
            chart_filename = chart_match.group(1).strip()
            answer = answer.replace(chart_match.group(0), "")
            
            # Read from the backend's local disk space and encode to Base64 to transport over the internet
            chart_path = Path(__file__).parent.parent / "app" / "static" / chart_filename
            if chart_path.exists():
                with open(chart_path, "rb") as image_file:
                    chart_base64 = base64.b64encode(image_file.read()).decode('utf-8')
                    
        return {
            "response": answer,
            "chart_base64": chart_base64
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
