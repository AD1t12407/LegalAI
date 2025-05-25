import logging
from typing import List, Optional
from langchain_core.documents import Document
from langchain.prompts import ChatPromptTemplate

from app.schemas.documents import (
    AmendmentSuggestion, 
    ClauseRiskAssessment, 
    ClauseType,
    ExtractedClause,
    RiskLevel
)
from app.core.config import settings
from app.core.llm import GroqChatModel

logger = logging.getLogger(__name__)

class AmendmentSuggesterAgent:
    """Agent for suggesting contract amendments."""
    
    def __init__(self):
        """Initialize the amendment suggester agent."""
        self.llm = GroqChatModel(
            model_name="llama3-70b-8192",
            temperature=0.2,  # Slightly higher for creative suggestions
            max_tokens=8192,
            top_p=0.9
        )
    
    def suggest_amendments(
        self,
        contract: Document,
        clauses: List[ExtractedClause],
        risk_assessments: List[ClauseRiskAssessment],
        policy_references: List[Document]
    ) -> List[AmendmentSuggestion]:
        """Suggest amendments for contract clauses.
        
        Args:
            contract: Contract document
            clauses: List of extracted clauses
            risk_assessments: Risk assessments for clauses
            policy_references: Relevant policy documents
            
        Returns:
            List of amendment suggestions
        """
        try:
            # Validate input
            if not isinstance(contract, Document) or not contract.page_content:
                raise ValueError("Invalid contract document")
                
            if not clauses:
                return []
                
            # Get policy text
            policy_texts = []
            for policy in policy_references:
                if isinstance(policy, Document) and policy.page_content:
                    policy_texts.append(policy.page_content)
            
            policy_text = "\n\n".join(policy_texts) if policy_texts else "No policy references available"
            
            # Create risk assessment map
            risk_map = {
                assessment.clause_id: assessment 
                for assessment in risk_assessments
            }
            
            amendments = []
            for clause in clauses:
                try:
                    # Get risk assessment
                    risk_assessment = risk_map.get(clause.clause_id)
                    if not risk_assessment:
                        continue
                        
                    # Only suggest amendments for medium/high risk clauses
                    if risk_assessment.risk_level == RiskLevel.LOW:
                        continue
                    
                    # Create messages for LLM
                    messages = [
                        {
                            "role": "system",
                            "content": "You are a legal expert specialized in contract amendments. Your task is to suggest "
                                      "improvements to contract clauses based on risk assessments and policy guidelines."
                        },
                        {
                            "role": "user",
                            "content": f"Clause Type: {clause.clause_type}\n\n"
                                      f"Original Text:\n{clause.text}\n\n"
                                      f"Risk Level: {risk_assessment.risk_level}\n"
                                      f"Risk Factors:\n{chr(10).join(risk_assessment.risk_factors)}\n\n"
                                      f"Policy Guidelines:\n{policy_text}\n\n"
                                      "Please suggest amendments that would:\n"
                                      "1. Reduce identified risks\n"
                                      "2. Improve compliance with policies\n"
                                      "3. Maintain the core business intent\n\n"
                                      "Format your response as:\n"
                                      "Suggested Text: [your suggested text]\n\n"
                                      "Reason: [explanation of changes]\n\n"
                                      "Priority: [1-5, where 5 is highest]"
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
                    
                    suggested_text = ""
                    reason = ""
                    priority = 3  # Default medium priority
                    
                    for section in sections:
                        if section.startswith("Suggested Text:"):
                            suggested_text = "\n".join(section.split("\n")[1:])
                        elif section.startswith("Reason:"):
                            reason = "\n".join(section.split("\n")[1:])
                        elif section.startswith("Priority:"):
                            try:
                                priority = int(section.split(":")[1].strip())
                            except:
                                priority = 3
                    
                    if suggested_text and reason:
                        amendments.append(AmendmentSuggestion(
                            clause_id=clause.clause_id,
                            clause_type=clause.clause_type,
                            original_text=clause.text,
                            suggested_text=suggested_text.strip(),
                            reason=reason.strip(),
                            priority=min(max(priority, 1), 5),  # Ensure 1-5 range
                            metadata={
                                "risk_level": risk_assessment.risk_level,
                                "risk_score": risk_assessment.risk_score
                            }
                        ))
                
                except Exception as e:
                    logger.error(f"Error suggesting amendment for clause {clause.clause_id}: {str(e)}")
                    amendments.append(AmendmentSuggestion(
                        clause_id=clause.clause_id,
                        clause_type=clause.clause_type,
                        original_text=clause.text,
                        suggested_text="[Error generating suggestion]",
                        reason=f"Error during analysis: {str(e)}",
                        priority=5,  # High priority since it needs attention
                        metadata={"error": str(e)}
                    ))
            
            return amendments
            
        except Exception as e:
            logger.error(f"Error in amendment suggestions: {str(e)}")
            return [AmendmentSuggestion(
                clause_id="error",
                clause_type=ClauseType.OTHER,
                original_text="Error processing contract",
                suggested_text="Please try again",
                reason=f"Error during analysis: {str(e)}",
                priority=5,
                metadata={"error": str(e)}
            )] 