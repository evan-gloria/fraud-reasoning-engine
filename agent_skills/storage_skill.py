import os
import json
from google.cloud import storage
from datetime import datetime, timezone

def upload_chart_to_gcs(local_file_path: str, bucket_name: str, 
                        transaction_id: str = "N/A", 
                        user_prompt: str = "N/A", 
                        sql_query: str = "N/A") -> str:
    """
    Uploads a visualization artifact to GCS with rich investigative metadata.
    
    Args:
        local_file_path: Path to the generated PNG or PPTX.
        bucket_name: GCS bucket for investigative artifacts.
        transaction_id: The ID of the current investigation session.
        user_prompt: The search query that generated this artifact.
        sql_query: The SQL query used to fetch the underlying data.
        
    Returns:
        The full gs:// URI of the uploaded artifact.
    """
    try:
        project_id = os.environ.get("GCP_PROJECT")
        if not project_id:
            raise ValueError("GCP_PROJECT environment variable is missing.")
            
        client = storage.Client(project=project_id)
        bucket = client.bucket(bucket_name)
        
        filename = os.path.basename(local_file_path)
        blob = bucket.blob(f"raw_visualizations/{filename}")
        
        # Attach investigative provenance metadata
        metadata = {
            "case_id": transaction_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "origin_prompt": user_prompt[:100], # Truncate for GCS metadata limits
            "logic_source_sql": sql_query[:100]
        }
        blob.metadata = metadata
        
        blob.upload_from_filename(local_file_path)
        
        uri = f"gs://{bucket_name}/{blob.name}"
        print(f"✅ [Storage Skill] Upload complete. URI: {uri}")
        return uri
        
    except Exception as e:
        print(f"⚠️ [Archival Error] Failed to upload artifact: {e}")
        return f"Error: {str(e)}"
