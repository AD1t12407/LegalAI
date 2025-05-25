import logging
from typing import List
from langchain_core.documents import Document
from langchain.prompts import ChatPromptTemplate

from app.schemas.documents import ClauseRiskAssessment
from app.core.config import settings
from app.core.llm import GroqChatModel

logger = logging.getLogger(__name__)

class SummaryAgent:
    """Agent for generating contract analysis summaries."""
    
    def __init__(self):
        """Initialize the summary agent."""
        self.llm = GroqChatModel(
            model_name="llama3-70b-8192",
            temperature=0.0,
            max_tokens=8192,
            top_p=0.9
        )
    
    def generate_summary(
        self,
        contract: Document,
        policies: List[Document],
        risk_assessments: List[ClauseRiskAssessment]
    ) -> str:
        """Generate a summary of the contract analysis.
        
        Args:
            contract: Contract document
            policies: List of policy documents
            risk_assessments: Risk assessments for clauses
            
        Returns:
            Summary text
        """
        try:
            # Validate input
            if not isinstance(contract, Document) or not contract.page_content:
                raise ValueError("Invalid contract document")
            
            # Get policy text
            policy_texts = []
            for policy in policies:
                if isinstance(policy, Document) and policy.page_content:
                    policy_texts.append(policy.page_content)
            
            policy_text = "\n\n".join(policy_texts) if policy_texts else "No policy references available"
            
            # Format risk assessments
            risk_text = ""
            if risk_assessments:
                risk_text = "Risk Assessments:\n"
                for assessment in risk_assessments:
                    risk_text += f"\nClause Type: {assessment.clause_type}\n"
                    risk_text += f"Risk Level: {assessment.risk_level}\n"
                    risk_text += f"Risk Score: {assessment.risk_score}\n"
                    risk_text += "Risk Factors:\n"
                    for factor in assessment.risk_factors:
                        risk_text += f"- {factor}\n"
            else:
                risk_text = "No risk assessments available"
            
            # Create messages for LLM
            messages = [
                {
                    "role": "system",
                    "content": "You are a legal expert specialized in contract analysis. Your task is to provide "
                              "clear and concise summaries of contract analyses, highlighting key risks and "
                              "recommendations."
                },
                {
                    "role": "user",
                    "content": f"Contract:\n{contract.page_content}\n\n"
                              f"Policies:\n{policy_text}\n\n"
                              f"Risk Assessments:\n{risk_text}\n\n"
                              "Please provide a comprehensive summary that includes:\n"
                              "1. Overall risk assessment\n"
                              "2. Key policy violations\n"
                              "3. Critical clauses requiring attention\n"
                              "4. Main recommendations\n"
                              "5. Next steps"
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
            
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return f"Error generating summary: {str(e)}" 