import os
import uuid
from datetime import datetime, timezone
from google.cloud import firestore

class HistoryManager:
    """
    Manages investigative conversation history using Google Cloud Firestore.
    Ensures persistent logs, zulu-standard timestamps, and case registry synchronization.
    """
    def __init__(self):
        self.project_id = os.environ.get("GCP_PROJECT")
        self.database_id = os.environ.get("GCP_FIRESTORE_DATABASE", "fraud-investigations")
        
        print(f"🕵️ [HistoryManager Audit] Project: {self.project_id}")
        print(f"🕵️ [HistoryManager Audit] Database Isolate: {self.database_id}")
        
        # Initialize Firestore with specific database isolate if provided
        try:
            self.db = firestore.Client(
                project=self.project_id,
                database=self.database_id
            )
        except Exception as e:
            print(f"⚠️ [Firestore Error] Failed to initialize: {e}")
            self.db = None

    def get_collection_counts(self):
        """Diagnostic tool to list all collections and document counts."""
        if not self.db: return {"error": "Firestore client not initialized"}
        try:
            collections = self.db.collections()
            results = {}
            for coll in collections:
                # Using a limit for speed during the audit
                count = len(list(coll.limit(100).stream()))
                results[coll.id] = count
            return results
        except Exception as e:
            return {"error": str(e)}

    def create_conversation(self, title: str = None) -> str:
        if not self.db: return str(uuid.uuid4())
        
        convo_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        doc_ref = self.db.collection("conversations").document(convo_id)
        doc_ref.set({
            "id": convo_id,
            "title": title or convo_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })
        return convo_id

    def get_conversations(self):
        if not self.db: return []
        
        # 1. Fetch from the Primary Collection
        convos_docs = self.db.collection("conversations").stream()
        
        # 2. Extract Registry
        registry = {}
        for d in convos_docs:
            data = d.to_dict()
            # Sanitize dates for JSON serialization
            for k, v in data.items():
                if hasattr(v, "isoformat"): data[k] = v.isoformat()
            registry[d.id] = {"id": d.id, **data}
            
        # 3. Sort by updated_at (Descending)
        # Fallback to current time if updated_at is missing for legacy docs
        sorted_registry = sorted(
            registry.values(), 
            key=lambda x: x.get("updated_at", x.get("created_at", datetime.now(timezone.utc))), 
            reverse=True
        )
        return sorted_registry

    def rename_conversation(self, conversation_id: str, new_title: str):
        if not self.db: return
        doc_ref = self.db.collection("conversations").document(conversation_id)
        doc_ref.update({
            "title": new_title,
            "updated_at": datetime.now(timezone.utc)
        })

    def delete_conversation(self, conversation_id: str):
        if not self.db: return
        # Delete messages first
        batch = self.db.batch()
        messages = self.db.collection("conversations").document(conversation_id).collection("messages").stream()
        for msg in messages:
            batch.delete(msg.reference)
        # Delete convo doc
        batch.delete(self.db.collection("conversations").document(conversation_id))
        batch.commit()

    def save_message(self, conversation_id: str, role: str, content: str, 
                     charts_base64=None, decks_base64=None, gcs_uris=None):
        if not self.db: return
        
        msg_id = str(uuid.uuid4())
        convo_ref = self.db.collection("conversations").document(conversation_id)
        msg_ref = convo_ref.collection("messages").document(msg_id)
        
        msg_data = {
            "id": msg_id,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc),
            "charts_base64": charts_base64 or [],
            "decks_base64": decks_base64 or [],
            "gcs_uris": gcs_uris or []
        }
        
        msg_ref.set(msg_data)
        
        # Update conversation heartbeat
        convo_ref.update({"updated_at": datetime.now(timezone.utc)})

    def get_history(self, conversation_id: str):
        if not self.db: return []
        
        messages = self.db.collection("conversations").document(conversation_id).collection("messages").order_by("created_at").stream()
        return [m.to_dict() for m in messages]
