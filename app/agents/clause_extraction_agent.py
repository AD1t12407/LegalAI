import re
import uuid
import logging
import spacy
from typing import Dict, List, Optional, Any, Tuple
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.schemas.documents import ExtractedClause, ClauseType
from app.core.llm import GroqChatModel

logger = logging.getLogger(__name__)

# Define regex patterns for common clause headers
CLAUSE_PATTERNS = {
    ClauseType.TERMINATION: r"(?i)(termination|cancellation|expiration)(\s+clause|\s+of\s+agreement|\s+and\s+suspension|\s+rights|\s+by|\s+for|\s+notice|\s+period|\:)",
    ClauseType.JURISDICTION: r"(?i)(jurisdiction|venue|forum|governing\s+law|choice\s+of\s+law|applicable\s+law)(\s+clause|\s+and|\s+selection|\s+provision|\:)",
    ClauseType.PAYMENT_TERMS: r"(?i)(payment\s+terms|fees|compensation|pricing|invoice|billing)(\s+clause|\s+and|\s+schedule|\s+provision|\:)",
    ClauseType.CONFIDENTIALITY: r"(?i)(confidentiality|non[\-\s]?disclosure|proprietary\s+information)(\s+clause|\s+and|\s+obligations|\s+provision|\:)",
    ClauseType.INTELLECTUAL_PROPERTY: r"(?i)(intellectual\s+property|ip|patent|copyright|trademark)(\s+clause|\s+rights|\s+ownership|\s+provision|\:)",
    ClauseType.LIABILITY: r"(?i)(liability|limitation\s+of\s+liability|disclaimer|warranties)(\s+clause|\s+and|\s+limitation|\s+provision|\:)",
    ClauseType.INDEMNIFICATION: r"(?i)(indemnification|indemnity|hold\s+harmless)(\s+clause|\s+and|\s+obligations|\s+provision|\:)",
    ClauseType.FORCE_MAJEURE: r"(?i)(force\s+majeure|act\s+of\s+god|unforeseen\s+event)(\s+clause|\s+and|\s+provision|\:)",
    ClauseType.ASSIGNMENT: r"(?i)(assignment|transfer|delegation|successors)(\s+clause|\s+and|\s+of\s+rights|\s+provision|\:)",
    ClauseType.GOVERNING_LAW: r"(?i)(governing\s+law|applicable\s+law|choice\s+of\s+law)(\s+clause|\s+and|\s+provision|\:)",
}

class ClauseExtractionAgent:
    """Agent for extracting legal clauses from contracts."""
    
    def __init__(self):
        """Initialize the clause extraction agent."""
        self.llm = GroqChatModel(
            model_name="llama3-70b-8192",  # Explicitly set the model name
            temperature=0.0,
            max_tokens=8192,
            top_p=0.9
        )
        
        # Load spaCy model if available, otherwise use regex-only approach
        try:
            self.nlp = spacy.load("en_core_web_lg")
            logger.info("Loaded spaCy model for clause extraction")
            self.use_spacy = True
        except Exception as e:
            logger.warning(f"Could not load spaCy model: {str(e)}. Using regex-only approach.")
            self.use_spacy = False
    
    def extract_clauses(self, document_text: str) -> List[ExtractedClause]:
        """Extract legal clauses from document text.
        
        Args:
            document_text: Full document text
            
        Returns:
            List of extracted clauses
        """
        logger.info("Extracting clauses from document")
        
        # First pass: Use regex to identify potential clause sections
        potential_clauses = self._extract_potential_clauses(document_text)
        
        # Second pass: Use LLM to validate and refine clauses
        extracted_clauses = self._refine_clauses_with_llm(potential_clauses)
        
        logger.info(f"Extracted {len(extracted_clauses)} clauses")
        return extracted_clauses
    
    def _extract_potential_clauses(self, document_text: str) -> List[Dict[str, Any]]:
        """Extract potential clauses using regex and NLP.
        
        Args:
            document_text: Full document text
            
        Returns:
            List of potential clauses
        """
        potential_clauses = []
        
        # Split document into pages if it contains page markers
        pages = re.split(r"---\s*Page\s+\d+\s*---", document_text)
        
        # Process each page
        for page_idx, page_text in enumerate(pages):
            page_num = page_idx + 1
            
            # Extract clauses using regex patterns
            for clause_type, pattern in CLAUSE_PATTERNS.items():
                matches = re.finditer(pattern, page_text)
                
                for match in matches:
                    # Get the start position of the match
                    start_pos = match.start()
                    
                    # Extract a chunk of text after the match (up to 2000 chars)
                    end_pos = min(start_pos + 2000, len(page_text))
                    clause_chunk = page_text[start_pos:end_pos]
                    
                    # Try to find a reasonable end to the clause (next section header)
                    section_headers = re.finditer(r"\n\s*\d+\.|\n\s*[A-Z][A-Z\s]+\:|"\
                                                r"\n\s*[A-Z][a-z]+\s+[A-Z][a-z]+\:", clause_chunk)
                    
                    # Get the position of the next section header
                    next_header_pos = None
                    for header_match in section_headers:
                        if header_match.start() > 100:  # Skip if too close to start
                            next_header_pos = header_match.start()
                            break
                    
                    # If found a next section, trim the clause
                    if next_header_pos:
                        clause_text = clause_chunk[:next_header_pos].strip()
                    else:
                        clause_text = clause_chunk.strip()
                    
                    # Add to potential clauses
                    potential_clauses.append({
                        "clause_type": clause_type,
                        "text": clause_text,
                        "page_number": page_num,
                        "start_index": start_pos,
                        "confidence": 0.7  # Initial confidence score
                    })
        
        # If spaCy is available, use it to improve extraction
        if self.use_spacy:
            potential_clauses = self._enhance_with_spacy(document_text, potential_clauses)
        
        return potential_clauses
    
    def _enhance_with_spacy(self, document_text: str, potential_clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance clause extraction using spaCy NLP.
        
        Args:
            document_text: Full document text
            potential_clauses: List of potential clauses from regex
            
        Returns:
            Enhanced list of potential clauses
        """
        # Process with spaCy
        doc = self.nlp(document_text[:1000000])  # Limit to prevent memory issues
        
        # Look for section headers and legal terms
        for sent in doc.sents:
            sent_text = sent.text.strip()
            
            # Skip short sentences
            if len(sent_text) < 10:
                continue
            
            # Check if sentence contains legal terminology
            legal_terms = ["agree", "shall", "party", "obligation", "right", "term", "condition", "law"]
            has_legal_term = any(term in sent_text.lower() for term in legal_terms)
            
            if has_legal_term:
                # Determine clause type based on content
                clause_type = self._determine_clause_type(sent_text)
                
                if clause_type:
                    # Get paragraph containing this sentence
                    para_start = max(0, document_text.rfind("\n\n", 0, document_text.find(sent_text)))
                    para_end = document_text.find("\n\n", document_text.find(sent_text))
                    if para_end == -1:
                        para_end = len(document_text)
                    
                    para_text = document_text[para_start:para_end].strip()
                    
                    # Add to potential clauses if not overlapping with existing ones
                    if not any(abs(c["start_index"] - para_start) < 200 for c in potential_clauses):
                        potential_clauses.append({
                            "clause_type": clause_type,
                            "text": para_text,
                            "page_number": None,  # Page number not tracked in this method
                            "start_index": para_start,
                            "confidence": 0.6  # Lower confidence for NLP-based extraction
                        })
        
        return potential_clauses
    
    def _determine_clause_type(self, text: str) -> Optional[ClauseType]:
        """Determine clause type based on text content.
        
        Args:
            text: Clause text
            
        Returns:
            Clause type or None if undetermined
        """
        text_lower = text.lower()
        
        # Simple keyword matching
        if any(kw in text_lower for kw in ["terminat", "cancel", "end of agreement"]):
            return ClauseType.TERMINATION
        elif any(kw in text_lower for kw in ["jurisdict", "venue", "forum", "court"]):
            return ClauseType.JURISDICTION
        elif any(kw in text_lower for kw in ["payment", "fee", "compensat", "invoice"]):
            return ClauseType.PAYMENT_TERMS
        elif any(kw in text_lower for kw in ["confidential", "disclos", "secret"]):
            return ClauseType.CONFIDENTIALITY
        elif any(kw in text_lower for kw in ["intellectual", "patent", "copyright", "trademark"]):
            return ClauseType.INTELLECTUAL_PROPERTY
        elif any(kw in text_lower for kw in ["liab", "warrant", "disclaimer"]):
            return ClauseType.LIABILITY
        elif any(kw in text_lower for kw in ["indemnif", "hold harmless"]):
            return ClauseType.INDEMNIFICATION
        elif any(kw in text_lower for kw in ["force majeure", "act of god", "unforeseen"]):
            return ClauseType.FORCE_MAJEURE
        elif any(kw in text_lower for kw in ["assign", "transfer", "delegat"]):
            return ClauseType.ASSIGNMENT
        elif any(kw in text_lower for kw in ["govern", "applicable law", "choice of law"]):
            return ClauseType.GOVERNING_LAW
        
        return None
    
    def _refine_clauses_with_llm(self, potential_clauses: List[Dict[str, Any]]) -> List[ExtractedClause]:
        """Refine and validate clauses using LLM.
        
        Args:
            potential_clauses: List of potential clauses
            
        Returns:
            List of validated and refined clauses
        """
        refined_clauses = []
        
        # Group clauses by type to avoid duplicates
        clauses_by_type = {}
        for clause in potential_clauses:
            clause_type = clause["clause_type"]
            if clause_type not in clauses_by_type:
                clauses_by_type[clause_type] = []
            clauses_by_type[clause_type].append(clause)
        
        # Process each clause type
        for clause_type, clauses in clauses_by_type.items():
            # Sort by confidence
            clauses.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            
            # Take the highest confidence clause for this type
            best_clause = clauses[0]
            
            # Use LLM to validate and refine the clause
            refined_text = self._refine_clause_text(best_clause["text"], clause_type)
            
            if refined_text:
                refined_clauses.append(
                    ExtractedClause(
                        clause_id=str(uuid.uuid4()),
                        clause_type=clause_type,
                        text=refined_text,
                        page_number=best_clause.get("page_number"),
                        start_index=best_clause.get("start_index"),
                        end_index=best_clause.get("start_index") + len(refined_text) if best_clause.get("start_index") else None,
                        meta={"confidence": best_clause.get("confidence", 0.7)}
                    )
                )
        
        return refined_clauses
    
    def _refine_clause_text(self, text: str, clause_type: ClauseType) -> Optional[str]:
        """Refine clause text using LLM.
        
        Args:
            text: Raw clause text
            clause_type: Type of clause
            
        Returns:
            Refined clause text or None if invalid
        """
        try:
            # Create system and user messages
            messages = [
                {
                    "role": "system",
                    "content": "You are a legal expert specialized in contract analysis. Your task is to extract and refine legal clauses from contracts."
                },
                {
                    "role": "user",
                    "content": f"Below is a potential {clause_type.value} clause from a contract. "
                              f"Please extract the complete clause text, removing any irrelevant text. "
                              f"If this is not a valid {clause_type.value} clause, respond with 'NOT_VALID'.\n\n"
                              f"Potential clause:\n{text}"
                }
            ]
            
            # Get response from LLM directly
            completion = self.llm.client.chat.completions.create(
                model=self.llm.model_name,
                messages=messages,
                temperature=self.llm.temperature,
                max_tokens=self.llm.max_tokens,
                top_p=self.llm.top_p
            )
            
            refined_text = completion.choices[0].message.content.strip()
            
            # Check if LLM considers this a valid clause
            if refined_text == "NOT_VALID":
                return None
            
            return refined_text
            
        except Exception as e:
            logger.error(f"Error refining clause with LLM: {str(e)}")
            # Return original text as fallback
            return text 