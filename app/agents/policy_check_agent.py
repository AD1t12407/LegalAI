import logging
from typing import List
from langchain_core.documents import Document
from langchain.prompts import ChatPromptTemplate
from datetime import datetime

from app.schemas.documents import PolicyCheckResult, ExtractedClause
from app.core.config import settings
from app.database.vector_store import VectorStore
from app.core.llm import GroqChatModel

logger = logging.getLogger(__name__)

class PolicyCheckAgent:
    """Agent for checking contracts against policy guidelines."""
    
    def __init__(self):
        """Initialize the policy check agent."""
        self.llm = GroqChatModel(
            model_name=settings.LLM_MODEL,
            temperature=0.0
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a legal policy compliance expert. Your task is to analyze a contract "
                      "against policy guidelines and identify violations and recommendations."),
            ("user", "Contract:\n{contract_text}\n\nPolicies:\n{policy_text}\n\n"
                    "Analyze the contract against these policies and identify:\n"
                    "1. Policy violations\n"
                    "2. Compliance score (0.0-1.0)\n"
                    "3. Specific recommendations for improvement")
        ])
        
        # Initialize vector store for policies
        self.policy_store = VectorStore("policies")
    
    def check_policies(self, contract: Document, policies: List[Document]) -> PolicyCheckResult:
        """Check a contract against policy guidelines.
        
        Args:
            contract: Contract document
            policies: List of policy documents
            
        Returns:
            Policy check result
        """
        try:
            # Ensure we have valid input
            if not isinstance(contract, Document) or not contract.page_content:
                raise ValueError("Invalid contract document")
            
            if not policies:
                return PolicyCheckResult(
                    policy_violations=["No policy documents found to check against"],
                    compliance_score=0.0,
                    recommendations=["Please upload policy documents first"],
                    metadata={"error": "no_policies"}
                )
            
            # Combine policy texts
            policy_texts = []
            for policy in policies:
                if isinstance(policy, Document) and policy.page_content:
                    policy_texts.append(policy.page_content)
            
            if not policy_texts:
                return PolicyCheckResult(
                    policy_violations=["No valid policy documents found"],
                    compliance_score=0.0,
                    recommendations=["Please check policy document format"],
                    metadata={"error": "invalid_policies"}
                )
            
            policy_text = "\n\n".join(policy_texts)
            
            # Run analysis
            chain = self.prompt | self.llm
            response = chain.invoke({
                "contract_text": contract.page_content,
                "policy_text": policy_text
            })
            
            # Parse response
            content = response.content
            sections = content.split("\n\n")
            
            violations = []
            recommendations = []
            compliance_score = 0.0
            
            for section in sections:
                if section.startswith("Policy violations:"):
                    violations = [v.strip() for v in section.split("\n")[1:] if v.strip()]
                elif section.startswith("Compliance score:"):
                    try:
                        score_text = section.split(":")[1].strip()
                        compliance_score = float(score_text)
                    except:
                        compliance_score = 0.0
                elif section.startswith("Recommendations:"):
                    recommendations = [r.strip() for r in section.split("\n")[1:] if r.strip()]
            
            return PolicyCheckResult(
                policy_violations=violations or ["No specific violations found"],
                compliance_score=compliance_score,
                recommendations=recommendations or ["No specific recommendations"],
                metadata={
                    "contract_id": contract.metadata.get("document_id"),
                    "analysis_timestamp": str(datetime.now())
                }
            )
            
        except Exception as e:
            logger.error(f"Error in policy check: {str(e)}")
            return PolicyCheckResult(
                policy_violations=["Error during policy check"],
                compliance_score=0.0,
                recommendations=["Please try again or contact support"],
                metadata={"error": str(e)}
            )

    def check_clause_against_policies(self, clause: ExtractedClause) -> List[Document]:
        """Check a clause against relevant policy documents.
        
        Args:
            clause: The clause to check
            
        Returns:
            List of relevant policy documents
        """
        try:
            # Get relevant policies using semantic search
            relevant_policies = self.policy_store.similarity_search(
                clause.text,
                k=3  # Get top 3 most relevant policies
            )
            
            return relevant_policies
            
        except Exception as e:
            logger.error(f"Error checking clause against policies: {str(e)}")
            return [] 