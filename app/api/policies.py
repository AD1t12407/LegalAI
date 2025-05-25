import os
import shutil
import uuid
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import List
from pathlib import Path
import logging

from app.core.config import settings
from app.schemas.documents import UploadResponse, DocumentType
from app.agents.doc_ingest_agent import DocIngestAgent

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize agents
doc_ingest_agent = DocIngestAgent()

@router.post("/upload", response_model=UploadResponse)
async def upload_policy(
    file: UploadFile = File(...),
):
    """Upload a policy document."""
    try:
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_ext = Path(file.filename).suffix
        
        # Create file path
        file_path = settings.POLICIES_DIR / f"{file_id}{file_ext}"
        
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Process the policy document
        document_id, _ = doc_ingest_agent.ingest_document(
            file_path=str(file_path),
            document_type=DocumentType.POLICY
        )
        
        return UploadResponse(
            file_id=document_id,
            filename=file.filename,
            content_type=file.content_type,
            size=os.path.getsize(file_path),
            message="Policy document uploaded and processed successfully"
        )
    
    except Exception as e:
        logger.error(f"Error uploading policy document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading policy document: {str(e)}")

@router.get("/")
async def list_policies():
    """List all policy documents."""
    try:
        # List all policy files
        policy_files = list(settings.POLICIES_DIR.glob("*.*"))
        
        policies = []
        for file_path in policy_files:
            policies.append({
                "file_id": file_path.stem,
                "filename": file_path.name,
                "size": os.path.getsize(file_path),
                "upload_date": os.path.getctime(file_path)
            })
        
        return {"policies": policies}
    
    except Exception as e:
        logger.error(f"Error listing policy documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing policy documents: {str(e)}")

@router.delete("/{policy_id}")
async def delete_policy(policy_id: str):
    """Delete a policy document."""
    try:
        # Find the policy file
        policy_files = list(settings.POLICIES_DIR.glob(f"{policy_id}.*"))
        
        if not policy_files:
            raise HTTPException(status_code=404, detail=f"Policy document with ID {policy_id} not found")
        
        # Delete the file
        for file_path in policy_files:
            os.remove(file_path)
        
        # TODO: Delete from vector store
        
        return {"status": "success", "message": f"Policy document {policy_id} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting policy document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting policy document: {str(e)}") 