import os
import uuid
import logging
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from pypdf import PdfReader
from langchain_core.documents import Document

from app.core.config import settings
from app.database.vector_store import VectorStore
from app.schemas.documents import ContractMetadata, DocumentType

logger = logging.getLogger(__name__)

class DocIngestAgent:
    """Agent for ingesting and processing documents."""
    
    def __init__(self):
        """Initialize the document ingestion agent."""
        self.contract_store = VectorStore("contracts")
        self.policy_store = VectorStore("policies")
    
    def ingest_document(
        self, 
        file_path: str, 
        document_type: DocumentType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, ContractMetadata]:
        """Process and ingest a document.
        
        Args:
            file_path: Path to the document file
            document_type: Type of document
            metadata: Optional metadata for the document
            
        Returns:
            Document ID and metadata
        """
        logger.info(f"Ingesting document: {file_path}")
        
        # Generate a unique document ID
        document_id = str(uuid.uuid4())
        
        # Extract text from document
        text, doc_metadata = self._extract_text_and_metadata(file_path)
        
        # Combine with provided metadata
        if metadata:
            doc_metadata.update(metadata)
        
        # Create document metadata
        filename = Path(file_path).name
        contract_metadata = ContractMetadata(
            title=doc_metadata.get("title", filename),
            document_type=document_type,
            parties=doc_metadata.get("parties", []),
            document_id=document_id,
            filename=filename,
            additional_metadata=doc_metadata
        )
        
        # Add document metadata to text
        full_text = f"Document ID: {document_id}\nTitle: {contract_metadata.title}\n\n{text}"
        
        # Add document ID to metadata
        doc_metadata.update({
            "document_id": document_id,
            "file_id": document_id,  # Store both for compatibility
            "title": contract_metadata.title,
            "document_type": document_type.value,
            "filename": filename
        })
        
        # Chunk and embed document
        chunks = VectorStore.chunk_document(
            text=full_text,
            metadata=doc_metadata
        )
        
        # Store in the appropriate vector store
        if document_type == DocumentType.POLICY:
            self.policy_store.add_documents(chunks)
        else:
            self.contract_store.add_documents(chunks)
        
        logger.info(f"Document ingested: {document_id}")
        return document_id, contract_metadata
    
    def _extract_text_and_metadata(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text and metadata from a document.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Extracted text and metadata
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == ".pdf":
            return self._extract_from_pdf(file_path)
        elif file_ext in [".docx", ".doc"]:
            raise NotImplementedError("Word document extraction not yet implemented")
        elif file_ext in [".txt", ".md"]:
            return self._extract_from_text(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    
    def _extract_from_pdf(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text and metadata from a PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text and metadata
        """
        metadata = {}
        full_text = ""
        
        try:
            # Extract with PyMuPDF (fitz)
            with fitz.open(file_path) as doc:
                metadata = {
                    "page_count": len(doc),
                    "title": doc.metadata.get("title", ""),
                    "author": doc.metadata.get("author", ""),
                    "subject": doc.metadata.get("subject", ""),
                    "keywords": doc.metadata.get("keywords", ""),
                    "creator": doc.metadata.get("creator", ""),
                    "producer": doc.metadata.get("producer", ""),
                }
                
                # Extract text from each page
                for page_num, page in enumerate(doc):
                    text = page.get_text()
                    full_text += f"\n\n--- Page {page_num + 1} ---\n\n{text}"
        
        except Exception as e:
            logger.error(f"Error extracting with PyMuPDF: {str(e)}")
            
            # Fallback to pypdf
            try:
                with open(file_path, "rb") as f:
                    reader = PdfReader(f)
                    metadata = {
                        "page_count": len(reader.pages),
                    }
                    
                    if reader.metadata:
                        metadata.update({
                            "title": reader.metadata.get("/Title", ""),
                            "author": reader.metadata.get("/Author", ""),
                            "subject": reader.metadata.get("/Subject", ""),
                            "keywords": reader.metadata.get("/Keywords", ""),
                            "creator": reader.metadata.get("/Creator", ""),
                            "producer": reader.metadata.get("/Producer", ""),
                        })
                    
                    # Extract text from each page
                    for page_num, page in enumerate(reader.pages):
                        text = page.extract_text()
                        full_text += f"\n\n--- Page {page_num + 1} ---\n\n{text}"
            
            except Exception as e2:
                logger.error(f"Error extracting with pypdf: {str(e2)}")
                raise ValueError(f"Could not extract text from PDF: {str(e2)}")
        
        return full_text, metadata
    
    def _extract_from_text(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """Extract text from a plain text file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            Extracted text and metadata
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            
            metadata = {
                "line_count": text.count("\n") + 1,
                "char_count": len(text),
            }
            
            return text, metadata
        
        except Exception as e:
            logger.error(f"Error extracting from text file: {str(e)}")
            raise ValueError(f"Could not extract text from file: {str(e)}")
    
    def get_document_by_id(self, document_id: str, k: int = 10) -> List[Document]:
        """Retrieve a document by ID.
        
        Args:
            document_id: Document ID
            k: Number of chunks to retrieve
            
        Returns:
            Document chunks
        """
        # Try both stores
        docs = self.contract_store.get_document_by_id(document_id)
        
        if not docs:
            docs = self.policy_store.get_document_by_id(document_id)
        
        return docs 