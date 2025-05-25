from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ClauseType(str, Enum):
    """Types of legal clauses in contracts."""
    TERMINATION = "termination"
    JURISDICTION = "jurisdiction"
    PAYMENT_TERMS = "payment_terms"
    CONFIDENTIALITY = "confidentiality"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    LIABILITY = "liability"
    INDEMNIFICATION = "indemnification"
    FORCE_MAJEURE = "force_majeure"
    ASSIGNMENT = "assignment"
    GOVERNING_LAW = "governing_law"
    OTHER = "other"
    PAYMENT = "payment"
    IP = "intellectual_property"
    COMPLIANCE = "compliance"
    AMENDMENTS = "amendments"


class RiskLevel(str, Enum):
    """Risk levels for contract clauses."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DocumentType(str, Enum):
    """Types of documents that can be analyzed."""
    CONTRACT = "contract"
    NDA = "nda"
    MSA = "msa"
    AGREEMENT = "agreement"
    POLICY = "policy"
    OTHER = "other"


class ContractMetadata(BaseModel):
    """Metadata for a contract document."""
    title: str
    document_type: DocumentType = DocumentType.CONTRACT
    parties: List[str] = []
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    document_id: Optional[str] = None
    filename: str
    upload_date: datetime = Field(default_factory=datetime.now)
    additional_metadata: Optional[Dict[str, Any]] = None


class ExtractedClause(BaseModel):
    """A legal clause extracted from a contract."""
    clause_id: str
    clause_type: ClauseType
    text: str
    page_number: Optional[int] = None
    start_index: int
    end_index: int
    meta: dict = Field(default_factory=dict)


class ClauseRiskAssessment(BaseModel):
    """Risk assessment for a contract clause."""
    clause_id: str
    clause_type: ClauseType
    risk_level: RiskLevel
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_factors: List[str]
    recommendations: List[str]
    reasons: List[str] = []
    policy_references: List[str] = []
    suggested_amendments: Optional[List[str]] = None


class PolicyReference(BaseModel):
    """Reference to a policy document."""
    policy_id: str
    policy_name: str
    section: Optional[str] = None
    text: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class PolicyCheckResult(BaseModel):
    """Result of checking a contract against policies."""
    policy_violations: List[str]
    compliance_score: float = Field(ge=0.0, le=1.0)
    recommendations: List[str]
    metadata: dict = Field(default_factory=dict)


class AmendmentSuggestion(BaseModel):
    """Suggested amendment for a contract clause."""
    clause_id: str
    clause_type: ClauseType
    original_text: str
    suggested_text: str
    reason: str
    priority: int = Field(ge=1, le=5)
    metadata: dict = Field(default_factory=dict)


class ContractAnalysis(BaseModel):
    """Complete analysis of a contract document."""
    contract_id: str
    metadata: ContractMetadata
    clauses: List[ExtractedClause] = []
    risk_assessments: List[ClauseRiskAssessment] = []
    policy_check: PolicyCheckResult
    amendment_suggestions: List[AmendmentSuggestion] = []
    overall_risk_score: float = Field(ge=0.0, le=1.0)
    overall_risk_level: RiskLevel
    summary: str
    recommendations: List[str] = []
    analysis_date: datetime = Field(default_factory=datetime.now)


class AnalysisStats(BaseModel):
    """Statistics about contract analysis."""
    total_contracts: int = 0
    total_clauses: int = 0
    risky_clauses: int = 0
    extracted_policies: int = 0
    avg_risk_score: float = 0.0
    avg_compliance_score: float = 0.0
    most_common_risks: List[str] = []
    most_common_violations: List[str] = []


class UploadResponse(BaseModel):
    """Response model for file upload endpoints."""
    file_id: str
    filename: str
    content_type: Optional[str] = None
    size: int
    upload_date: datetime = Field(default_factory=datetime.now)
    status: str = "success"
    message: str = "File uploaded successfully"


class ErrorResponse(BaseModel):
    """Standard error response model."""
    status: str = "error"
    message: str
    detail: Optional[str] = None 