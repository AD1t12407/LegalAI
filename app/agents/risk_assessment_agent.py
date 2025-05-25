import logging
from typing import List, Tuple
from langchain_core.documents import Document
from langchain.prompts import ChatPromptTemplate

from app.schemas.documents import ClauseRiskAssessment, ClauseType, RiskLevel, ExtractedClause
from app.core.config import settings
from app.core.llm import GroqChatModel

logger = logging.getLogger(__name__)

class RiskAssessmentAgent:
    """Agent for assessing contract risks."""
    
    def __init__(self):
        """Initialize the risk assessment agent."""
        self.llm = GroqChatModel(
            model_name="llama3-70b-8192",
            temperature=0.0,
            max_tokens=8192,
            top_p=0.9
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a legal risk assessment expert. Your task is to analyze contract clauses "
                      "and identify potential risks based on policy guidelines.\n\n"
                      "For each clause, provide a risk assessment in the following format:\n"
                      "Risk Level: [high/medium/low]\n"
                      "Risk Score: [0.0-1.0]\n"
                      "Risk Factors:\n"
                      "- [factor 1]\n"
                      "- [factor 2]\n"
                      "Recommendations:\n"
                      "- [recommendation 1]\n"
                      "- [recommendation 2]"),
            ("user", "Clause Type: {clause_type}\n\nClause Text:\n{clause_text}\n\nPolicies:\n{policy_text}\n\n"
                    "Analyze this clause and provide:\n"
                    "1. Risk level (high/medium/low)\n"
                    "2. Risk score (0.0-1.0)\n"
                    "3. Specific risk factors\n"
                    "4. Recommendations for improvement")
        ])
        
        self.clause_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a legal risk assessment expert. Your task is to analyze a specific "
                      "contract clause and identify potential risks based on policy guidelines."),
            ("user", "Clause:\n{clause_text}\n\nPolicies:\n{policy_text}\n\n"
                    "Analyze this clause and provide:\n"
                    "1. Risk level (high/medium/low)\n"
                    "2. Risk score (0.0-1.0)\n"
                    "3. Specific risk factors\n"
                    "4. Recommendations for improvement")
        ])
    
    def assess_clause_risk(
        self,
        clause: ExtractedClause,
        policy_references: List[Document]
    ) -> ClauseRiskAssessment:
        """Assess the risk level of a contract clause.
        
        Args:
            clause: The clause to assess
            policy_references: Relevant policy documents
            
        Returns:
            Risk assessment result
        """
        try:
            # Validate input
            if not isinstance(clause, ExtractedClause):
                raise ValueError("Invalid clause object")
            
            # Get policy text
            policy_texts = []
            for policy in policy_references:
                if isinstance(policy, Document) and policy.page_content:
                    policy_texts.append(policy.page_content)
            
            policy_text = "\n\n".join(policy_texts) if policy_texts else "No policy references available"
            
            # Create messages for the LLM
            messages = [
                {
                    "role": "system",
                    "content": "You are a legal risk assessment expert. Your task is to analyze contract clauses "
                              "and identify potential risks based on policy guidelines.\n\n"
                              "For each clause, provide a risk assessment in the following format:\n"
                              "Risk Level: [high/medium/low]\n"
                              "Risk Score: [0.0-1.0]\n"
                              "Risk Factors:\n"
                              "- [factor 1]\n"
                              "- [factor 2]\n"
                              "Recommendations:\n"
                              "- [recommendation 1]\n"
                              "- [recommendation 2]"
                },
                {
                    "role": "user",
                    "content": f"Clause Type: {clause.clause_type}\n\n"
                              f"Clause Text:\n{clause.text}\n\n"
                              f"Policies:\n{policy_text}\n\n"
                              "Analyze this clause and provide:\n"
                              "1. Risk level (high/medium/low)\n"
                              "2. Risk score (0.0-1.0)\n"
                              "3. Specific risk factors\n"
                              "4. Recommendations for improvement"
                }
            ]
            
            # Get response from LLM
            completion = self.llm.client.chat.completions.create(
                model=self.llm.model_name,
                messages=messages,
                temperature=self.llm.temperature,
                max_tokens=self.llm.max_tokens,
                top_p=self.llm.top_p
            )
            
            # Parse response
            content = completion.choices[0].message.content
            sections = content.split("\n\n")
            
            risk_level = RiskLevel.MEDIUM  # Default
            risk_score = 0.5  # Default
            risk_factors = []
            recommendations = []
            reasons = []
            
            for section in sections:
                if section.startswith("Risk Level:"):
                    level_text = section.split(":")[1].strip().lower()
                    if level_text in ["low", "medium", "high"]:
                        risk_level = RiskLevel(level_text)
                elif section.startswith("Risk Score:"):
                    try:
                        score_text = section.split(":")[1].strip()
                        risk_score = float(score_text)
                    except:
                        risk_score = 0.5
                elif section.startswith("Risk Factors:"):
                    risk_factors = [f.strip() for f in section.split("\n")[1:] if f.strip()]
                elif section.startswith("Recommendations:"):
                    recommendations = [r.strip() for r in section.split("\n")[1:] if r.strip()]
                elif section.startswith("Reasons:"):
                    reasons = [r.strip() for r in section.split("\n")[1:] if r.strip()]
            
            return ClauseRiskAssessment(
                clause_id=clause.clause_id,
                clause_type=clause.clause_type,
                risk_level=risk_level,
                risk_score=risk_score,
                risk_factors=risk_factors or ["No specific risk factors identified"],
                recommendations=recommendations or ["No specific recommendations"],
                reasons=reasons or ["Risk assessment based on general analysis"],
                policy_references=[p.metadata.get("document_id", "unknown") for p in policy_references if isinstance(p, Document)]
            )
            
        except Exception as e:
            logger.error(f"Error in clause risk assessment: {str(e)}")
            return ClauseRiskAssessment(
                clause_id=getattr(clause, 'clause_id', 'unknown'),
                clause_type=getattr(clause, 'clause_type', ClauseType.OTHER),
                risk_level=RiskLevel.HIGH,  # Default to high risk on error
                risk_score=1.0,  # Default to highest risk on error
                risk_factors=["Error during risk assessment"],
                recommendations=["Please review manually or try again"],
                reasons=[f"Error: {str(e)}"],
                policy_references=[]
            )
    
    def calculate_overall_risk(
        self,
        risk_assessments: List[ClauseRiskAssessment]
    ) -> Tuple[float, RiskLevel]:
        """Calculate overall risk score and level from clause assessments.
        
        Args:
            risk_assessments: List of clause risk assessments
            
        Returns:
            Tuple of (risk_score, risk_level)
        """
        try:
            if not risk_assessments:
                return 0.5, RiskLevel.MEDIUM
            
            # Calculate weighted average of risk scores
            total_score = sum(assessment.risk_score for assessment in risk_assessments)
            avg_score = total_score / len(risk_assessments)
            
            # Determine overall risk level
            if avg_score >= 0.7:
                risk_level = RiskLevel.HIGH
            elif avg_score >= 0.4:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            
            return avg_score, risk_level
            
        except Exception as e:
            logger.error(f"Error calculating overall risk: {str(e)}")
            return 1.0, RiskLevel.HIGH  # Default to high risk on error 