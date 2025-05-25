from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging
from collections import Counter

from app.schemas.documents import (
    ContractAnalysis,
    ExtractedClause,
    ClauseRiskAssessment,
    RiskLevel,
    AnalysisStats,
    PolicyCheckResult,
    AmendmentSuggestion
)
from app.database.vector_store import VectorStore
from app.agents.policy_check_agent import PolicyCheckAgent
from app.agents.risk_assessment_agent import RiskAssessmentAgent
from app.agents.amendment_suggester_agent import AmendmentSuggesterAgent
from app.agents.summary_agent import SummaryAgent
from app.agents.doc_ingest_agent import DocIngestAgent
from app.agents.clause_extraction_agent import ClauseExtractionAgent
from langchain.schema import Document

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize vector stores and agents
contract_store = VectorStore("contracts")
policy_store = VectorStore("policies")
policy_check_agent = PolicyCheckAgent()
risk_assessment_agent = RiskAssessmentAgent()
amendment_suggester_agent = AmendmentSuggesterAgent()
summary_agent = SummaryAgent()
doc_ingest_agent = DocIngestAgent()
clause_extraction_agent = ClauseExtractionAgent()

@router.get("/{contract_id}/policy-check", response_model=PolicyCheckResult)
async def check_contract_against_policies(contract_id: str):
    """Check a contract against policy guidelines."""
    try:
        # Get contract document
        contract_docs = doc_ingest_agent.get_document_by_id(contract_id)
        if not contract_docs:
            raise HTTPException(status_code=404, detail=f"Contract with ID {contract_id} not found")
        
        # Ensure contract_docs is a list
        if not isinstance(contract_docs, list):
            contract_docs = [contract_docs]
            
        # Combine chunks into full document
        document_text = "\n\n".join([chunk.page_content for chunk in contract_docs if hasattr(chunk, 'page_content')])
        
        if not document_text:
            raise HTTPException(status_code=500, detail="Invalid document format returned from storage")
            
        contract_doc = Document(
            page_content=document_text,
            metadata={"document_id": contract_id}
        )
        
        # Get policy documents
        policy_docs = policy_check_agent.policy_store.get_all_documents()
        if not policy_docs:
            raise HTTPException(status_code=404, detail="No policy documents found")
        
        # Run policy check
        result = policy_check_agent.check_policies(contract_doc, policy_docs)
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking contract against policies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking contract against policies: {str(e)}")

@router.get("/{contract_id}/risks")
async def get_contract_risks(contract_id: str):
    """Get risk assessment for a contract."""
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
        raise HTTPException(status_code=500, detail=f"Error retrieving contract risks: {str(e)}")

@router.get("/{contract_id}/amendments")
async def get_contract_amendments(contract_id: str):
    """Get amendment suggestions for a contract."""
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
            
        contract_doc = Document(
            page_content=document_text,
            metadata={"document_id": contract_id}
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
        if not policy_docs:
            logger.warning("No policy documents found")
            policy_docs = []
        
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

@router.get("/{contract_id}/summary")
async def get_contract_summary(contract_id: str):
    """Get a summary of the contract analysis."""
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
            
        contract_doc = Document(
            page_content=document_text,
            metadata={"document_id": contract_id}
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
        if not policy_docs:
            logger.warning("No policy documents found")
            policy_docs = []
        
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

@router.get("/stats", response_model=AnalysisStats)
async def get_analysis_stats():
    """Get statistics about contract analyses."""
    try:
        # Get all contract documents
        contracts = doc_ingest_agent.get_all_documents()
        
        # Initialize counters
        total_contracts = len(contracts)
        total_clauses = 0
        risky_clauses = 0
        extracted_policies = 0
        risk_scores = []
        compliance_scores = []
        all_risks = []
        all_violations = []
        
        # Get all policy documents
        policy_docs = policy_check_agent.policy_store.get_all_documents()
        extracted_policies = len(policy_docs)
        
        # Process each contract
        for contract in contracts:
            metadata = contract.metadata
            
            # Count clauses
            if "num_clauses" in metadata:
                total_clauses += metadata["num_clauses"]
            if "risky_clauses" in metadata:
                risky_clauses += metadata["risky_clauses"]
                
            # Track scores
            if "risk_score" in metadata:
                risk_scores.append(float(metadata["risk_score"]))
            if "compliance_score" in metadata:
                compliance_scores.append(float(metadata["compliance_score"]))
                
            # Track risks and violations
            if "risk_reasons" in metadata:
                all_risks.extend(metadata["risk_reasons"])
            if "policy_violations" in metadata:
                all_violations.extend(metadata["policy_violations"])
        
        # Calculate averages
        avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
        avg_compliance_score = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0.0
        
        # Get most common issues
        risk_counter = Counter(all_risks)
        violation_counter = Counter(all_violations)
        most_common_risks = [risk for risk, _ in risk_counter.most_common(5)]
        most_common_violations = [violation for violation, _ in violation_counter.most_common(5)]
        
        return AnalysisStats(
            total_contracts=total_contracts,
            total_clauses=total_clauses,
            risky_clauses=risky_clauses,
            extracted_policies=extracted_policies,
            avg_risk_score=round(avg_risk_score, 2),
            avg_compliance_score=round(avg_compliance_score, 2),
            most_common_risks=most_common_risks,
            most_common_violations=most_common_violations
        )
    
    except Exception as e:
        logger.error(f"Error retrieving analysis stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving analysis stats: {str(e)}")

@router.get("/{contract_id}/clauses")
async def get_contract_clauses(
    contract_id: str,
    clause_type: Optional[str] = Query(None),
    risk_level: Optional[RiskLevel] = Query(None)
):
    """Get clauses from a contract with optional filtering."""
    try:
        # TODO: Retrieve contract clauses from database
        # For now, just return a placeholder
        raise HTTPException(status_code=501, detail="Contract clauses retrieval not yet implemented")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving contract clauses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving contract clauses: {str(e)}") 