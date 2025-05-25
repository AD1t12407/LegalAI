import os
import shutil
import uuid
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Form, Depends
from typing import List, Optional
from pathlib import Path
import logging
from langchain_core.documents import Document

from app.core.config import settings
from app.schemas.documents import (
    UploadResponse, 
    DocumentType,
    ClauseType,
    ContractAnalysis,
    ContractMetadata
)
from app.agents.doc_ingest_agent import DocIngestAgent
from app.agents.clause_extraction_agent import ClauseExtractionAgent
from app.agents.policy_check_agent import PolicyCheckAgent
from app.agents.risk_assessment_agent import RiskAssessmentAgent
from app.agents.amendment_suggester_agent import AmendmentSuggesterAgent
from app.agents.summary_agent import SummaryAgent

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize agents
doc_ingest_agent = DocIngestAgent()
clause_extraction_agent = ClauseExtractionAgent()
policy_check_agent = PolicyCheckAgent()
risk_assessment_agent = RiskAssessmentAgent()
amendment_suggester_agent = AmendmentSuggesterAgent()
summary_agent = SummaryAgent()

@router.post("/upload")
async def upload_contract(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.CONTRACT)
) -> UploadResponse:
    """Upload and process a contract document.
    
    Args:
        file: Contract file
        document_type: Type of document
        
    Returns:
        Upload response with file ID
    """
    try:
        # Create temp directory if it doesn't exist
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        
        # Save uploaded file
        temp_file = temp_dir / file.filename
        try:
            contents = await file.read()
            temp_file.write_bytes(contents)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error saving file: {str(e)}"
            )
        
        # Process contract
        try:
            analysis = process_contract(str(temp_file), document_type)
            
            # Return upload response
            return UploadResponse(
                file_id=analysis.contract_id,
                filename=file.filename,
                content_type=file.content_type,
                size=len(contents),
                status="success",
                message="Contract uploaded successfully"
            )
            
        finally:
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading contract: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading contract: {str(e)}"
        )

@router.get("/{contract_id}")
async def get_contract(contract_id: str) -> ContractAnalysis:
    """Get analysis results for a contract.
    
    Args:
        contract_id: Contract ID
        
    Returns:
        Contract analysis
    """
    try:
        # Get document from vector store
        document_chunks = doc_ingest_agent.get_document_by_id(contract_id)
        if not document_chunks:
            raise HTTPException(
                status_code=404,
                detail=f"Contract with ID {contract_id} not found"
            )
        
        # Combine chunks into full document
        document_text = "\n\n".join([chunk.page_content for chunk in document_chunks])
        contract_doc = Document(
            page_content=document_text,
            metadata={"document_id": contract_id}
        )
        
        # Extract clauses
        clauses = clause_extraction_agent.extract_clauses(document_text)
        
        # Get policy documents
        policy_docs = policy_check_agent.policy_store.get_all_documents()
        if not policy_docs:
            logger.warning("No policy documents found")
            policy_docs = []
        
        # Check policies
        policy_check_result = policy_check_agent.check_policies(contract_doc, policy_docs)
        
        # Check clauses against policies and assess risks
        risk_assessments = []
        for clause in clauses:
            # Get relevant policies
            policy_references = policy_check_agent.check_clause_against_policies(clause)
            
            # Assess risk
            risk_assessment = risk_assessment_agent.assess_clause_risk(
                clause=clause,
                policy_references=policy_references
            )
            risk_assessments.append(risk_assessment)
        
        # Calculate overall risk
        overall_risk_score, overall_risk_level = risk_assessment_agent.calculate_overall_risk(
            risk_assessments
        )
        
        # Generate amendment suggestions
        amendments = amendment_suggester_agent.suggest_amendments(
            contract=contract_doc,
            clauses=clauses,
            risk_assessments=risk_assessments,
            policy_references=policy_docs
        )
        
        # Generate summary
        summary = summary_agent.generate_summary(
            contract=contract_doc,
            policies=policy_docs,
            risk_assessments=risk_assessments
        )
        
        # Get metadata from first chunk
        metadata = document_chunks[0].metadata
        contract_metadata = ContractMetadata(
            title=metadata.get("title", "Unknown"),
            document_type=DocumentType(metadata.get("document_type", "contract")),
            document_id=contract_id,
            filename=metadata.get("filename", "Unknown"),
            additional_metadata=metadata
        )
        
        return ContractAnalysis(
            contract_id=contract_id,
            metadata=contract_metadata,
            clauses=clauses,
            risk_assessments=risk_assessments,
            policy_check=policy_check_result,
            amendment_suggestions=amendments,
            overall_risk_score=overall_risk_score,
            overall_risk_level=overall_risk_level,
            summary=summary,
            recommendations=policy_check_result.recommendations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contract: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting contract: {str(e)}"
        )

@router.post("/analyze/{file_id}", response_model=ContractAnalysis)
async def analyze_contract(
    file_id: str,
    document_type: DocumentType = DocumentType.CONTRACT
):
    """Analyze a previously uploaded contract."""
    try:
        # Find the contract file
        contract_files = list(settings.CONTRACTS_DIR.glob(f"{file_id}.*"))
        
        if not contract_files:
            raise HTTPException(status_code=404, detail=f"Contract with ID {file_id} not found")
        
        # Get the first matching file
        file_path = contract_files[0]
        
        # Process the contract
        analysis = process_contract(str(file_path), document_type)
        return analysis
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing contract: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing contract: {str(e)}")

@router.get("/{contract_id}", response_model=ContractAnalysis)
async def get_contract_analysis(contract_id: str):
    """Get the analysis for a specific contract."""
    try:
        # Retrieve contract chunks from vector store
        contract_chunks = doc_ingest_agent.get_document_by_id(contract_id)
        
        if not contract_chunks:
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
        
        # TODO: Retrieve analysis from database or recreate it
        # For now, just return a placeholder
        raise HTTPException(status_code=501, detail="Retrieving existing analysis not yet implemented")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving contract analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving contract analysis: {str(e)}")

@router.delete("/{contract_id}")
async def delete_contract(contract_id: str):
    """Delete a contract and its analysis."""
    try:
        # Find the contract file
        contract_files = list(settings.CONTRACTS_DIR.glob(f"{contract_id}.*"))
        
        if not contract_files:
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
        
        # Delete the file
        for file_path in contract_files:
            os.remove(file_path)
        
        # TODO: Delete from vector store
        
        return {"status": "success", "message": f"Contract {contract_id} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contract: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting contract: {str(e)}")

def process_contract(file_path: str, document_type: DocumentType) -> ContractAnalysis:
    """Process a contract document through all agents.
    
    Args:
        file_path: Path to the contract file
        document_type: Type of document
        
    Returns:
        Contract analysis
    """
    logger.info(f"Processing contract: {file_path}")
    
    try:
        # Step 1: Ingest document
        document_id, contract_metadata = doc_ingest_agent.ingest_document(
            file_path=file_path,
            document_type=document_type
        )
        
        # Step 2: Get document from vector store
        document = doc_ingest_agent.get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail=f"Contract with ID {document_id} not found")
        
        # Create contract document
        contract_doc = Document(
            page_content=document.page_content,
            metadata={"document_id": document_id}
        )
        
        # Step 3: Extract clauses
        clauses = clause_extraction_agent.extract_clauses(contract_doc.page_content)
        
        # Step 4: Get policy documents
        policy_docs = policy_check_agent.policy_store.get_all_documents()
        if not policy_docs:
            logger.warning("No policy documents found")
            policy_docs = []
        
        # Step 5: Check policies
        policy_check_result = policy_check_agent.check_policies(contract_doc, policy_docs)
        
        # Step 6: Check clauses against policies and assess risks
        risk_assessments = []
        for clause in clauses:
            # Get relevant policies
            policy_references = policy_check_agent.check_clause_against_policies(clause)
            
            # Assess risk
            risk_assessment = risk_assessment_agent.assess_clause_risk(
                clause=clause,
                policy_references=policy_references
            )
            risk_assessments.append(risk_assessment)
        
        # Step 7: Calculate overall risk
        overall_risk_score, overall_risk_level = risk_assessment_agent.calculate_overall_risk(
            risk_assessments
        )
        
        # Step 8: Generate amendment suggestions
        amendments = amendment_suggester_agent.suggest_amendments(
            contract=contract_doc,
            clauses=clauses,
            risk_assessments=risk_assessments,
            policy_references=policy_docs
        )
        
        # Step 9: Generate summary
        summary = summary_agent.generate_summary(
            contract=contract_doc,
            policies=policy_docs,
            risk_assessments=risk_assessments
        )
        
        return ContractAnalysis(
            contract_id=document_id,
            metadata=contract_metadata,
            clauses=clauses,
            risk_assessments=risk_assessments,
            policy_check=policy_check_result,
            amendment_suggestions=amendments,
            overall_risk_score=overall_risk_score,
            overall_risk_level=overall_risk_level,
            summary=summary,
            recommendations=policy_check_result.recommendations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing contract: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing contract: {str(e)}"
        )

@router.get("/{contract_id}/clauses")
async def get_contract_clauses(contract_id: str):
    """Get clauses from a contract."""
    try:
        # Get contract from vector store
        contract_chunks = doc_ingest_agent.get_document_by_id(contract_id)
        
        if not contract_chunks:
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
        
        # Ensure contract_chunks is a list
        if not isinstance(contract_chunks, list):
            contract_chunks = [contract_chunks]
            
        # Combine chunks into full document
        document_text = "\n\n".join([chunk.page_content for chunk in contract_chunks if hasattr(chunk, 'page_content')])
        
        if not document_text:
            raise HTTPException(status_code=500, detail="Invalid document format returned from storage")
            
        # Extract clauses
        clauses = clause_extraction_agent.extract_clauses(document_text)
        
        return {"clauses": clauses}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting clauses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting clauses: {str(e)}")

@router.get("/analysis/{contract_id}/policy-check")
async def check_contract_policies(contract_id: str):
    """Check contract against policies."""
    try:
        # Get contract from vector store
        contract_chunks = doc_ingest_agent.get_document_by_id(contract_id)
        
        if not contract_chunks:
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
        
        # Combine chunks into full document
        document_text = "\n\n".join([chunk.page_content for chunk in contract_chunks])
        contract_doc = Document(
            page_content=document_text,
            metadata={"contract_id": contract_id}
        )
        
        # Get policies
        policy_docs = policy_check_agent.policy_store.get_all_documents()
        
        # Check policies
        policy_check_result = policy_check_agent.check_policies(contract_doc, policy_docs)
        
        return policy_check_result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking policies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking policies: {str(e)}")

@router.get("/{contract_id}/risks")
async def get_contract_risks(contract_id: str):
    """Get risk assessment for a contract."""
    try:
        # Get contract from vector store
        contract_chunks = doc_ingest_agent.get_document_by_id(contract_id)
        if not contract_chunks:
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
        
        # Combine chunks into full document
        document_text = "\n\n".join([chunk.page_content for chunk in contract_chunks])
        contract_doc = Document(
            page_content=document_text,
            metadata={"document_id": contract_id}
        )
        
        # Extract clauses
        clauses = clause_extraction_agent.extract_clauses(document_text)
        
        # Get policy documents
        policy_docs = policy_check_agent.policy_store.get_all_documents()
        if not policy_docs:
            logger.warning("No policy documents found")
            policy_docs = []
        
        # Check clauses against policies and assess risks
        risk_assessments = []
        for clause in clauses:
            # Get relevant policies
            policy_references = policy_check_agent.check_clause_against_policies(clause)
            
            # Assess risk
            risk_assessment = risk_assessment_agent.assess_clause_risk(
                clause=clause,
                policy_references=policy_references
            )
            risk_assessments.append(risk_assessment)
        
        # Calculate overall risk
        overall_risk_score, overall_risk_level = risk_assessment_agent.calculate_overall_risk(
            risk_assessments
        )
        
        return {
            "contract_id": contract_id,
            "risk_assessments": risk_assessments,
            "overall_risk_score": overall_risk_score,
            "overall_risk_level": overall_risk_level
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving contract risks: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving contract risks: {str(e)}"
        )

@router.get("/analysis/{contract_id}/amendments")
async def suggest_amendments(contract_id: str):
    """Suggest amendments for a contract."""
    try:
        # Get contract from vector store
        contract_chunks = doc_ingest_agent.get_document_by_id(contract_id)
        
        if not contract_chunks:
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
        
        # Combine chunks into full document
        document_text = "\n\n".join([chunk.page_content for chunk in contract_chunks])
        contract_doc = Document(
            page_content=document_text,
            metadata={"contract_id": contract_id}
        )
        
        # Extract clauses
        clauses = clause_extraction_agent.extract_clauses(document_text)
        
        # Get risk assessments
        risk_assessments = []
        for clause in clauses:
            # Get relevant policies
            policy_references = policy_check_agent.check_clause_against_policies(clause)
            
            # Assess risk
            risk_assessment = risk_assessment_agent.assess_clause_risk(
                clause=clause,
                policy_references=policy_references
            )
            risk_assessments.append(risk_assessment)
        
        # Get policy documents
        policy_docs = policy_check_agent.policy_store.get_all_documents()
        
        # Generate amendment suggestions
        amendments = amendment_suggester_agent.suggest_amendments(
            contract=contract_doc,
            clauses=clauses,
            risk_assessments=risk_assessments,
            policy_references=policy_docs
        )
        
        return {"amendments": amendments}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suggesting amendments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error suggesting amendments: {str(e)}")

@router.get("/analysis/{contract_id}/summary")
async def get_contract_summary(contract_id: str):
    """Get a summary of the contract analysis."""
    try:
        # Get contract from vector store
        contract_chunks = doc_ingest_agent.get_document_by_id(contract_id)
        
        if not contract_chunks:
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
        
        # Combine chunks into full document
        document_text = "\n\n".join([chunk.page_content for chunk in contract_chunks])
        contract_doc = Document(
            page_content=document_text,
            metadata={"contract_id": contract_id}
        )
        
        # Get risk assessments
        risk_assessments = []
        clauses = clause_extraction_agent.extract_clauses(document_text)
        for clause in clauses:
            # Get relevant policies
            policy_references = policy_check_agent.check_clause_against_policies(clause)
            
            # Assess risk
            risk_assessment = risk_assessment_agent.assess_clause_risk(
                clause=clause,
                policy_references=policy_references
            )
            risk_assessments.append(risk_assessment)
        
        # Get policy documents
        policy_docs = policy_check_agent.policy_store.get_all_documents()
        
        # Generate summary
        summary = summary_agent.generate_summary(
            contract=contract_doc,
            policies=policy_docs,
            risk_assessments=risk_assessments
        )
        
        return {"summary": summary}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}") 