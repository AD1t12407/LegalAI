import os
import chromadb
import logging
import numpy as np
import pinecone
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from sentence_transformers import SentenceTransformer
from langchain_core.documents import Document
from langchain_chroma import Chroma
from chromadb.config import Settings
from langchain_pinecone import PineconeVectorStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings

from app.core.config import settings

logger = logging.getLogger(__name__)

class VectorStore:
    """Vector store interface for document storage and retrieval."""
    
    def __init__(self, collection_name: str):
        """Initialize the vector store.
        
        Args:
            collection_name: Name of the collection
        """
        self.collection_name = collection_name
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL
        )
        self.persistent_dir = settings.EMBEDDINGS_DIR / collection_name
        self.persistent_dir.mkdir(exist_ok=True, parents=True)
        
        # Initialize Chroma store with HuggingFace embeddings
        self.vector_store = Chroma(
            collection_name=collection_name,
            persist_directory=str(settings.VECTOR_STORE_DIR),
            embedding_function=self.embeddings,
            client_settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        logger.info(f"Loaded ChromaDB collection: {collection_name}")
        
        # Initialize based on the selected vector store type
        if settings.VECTOR_DB_TYPE == "pinecone":
            self._init_pinecone()
    
    def _init_pinecone(self):
        """Initialize Pinecone vector store."""
        if not settings.PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY environment variable not set")
        
        pinecone.init(
            api_key=settings.PINECONE_API_KEY,
            environment=settings.PINECONE_ENV
        )
        
        # Create index if it doesn't exist
        if self.collection_name not in pinecone.list_indexes():
            pinecone.create_index(
                name=self.collection_name,
                dimension=768,  # Dimensions for sentence-transformers embeddings
                metric="cosine"
            )
        
        self.vector_store = PineconeVectorStore(
            index_name=self.collection_name,
            embedding=self.embeddings
        )
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to the vector store.
        
        Args:
            documents: List of documents to add
            
        Returns:
            List of document IDs
        """
        logger.info(f"Adding {len(documents)} documents to {self.collection_name}")
        
        try:
            # Add document IDs to metadata if not present
            for i, doc in enumerate(documents):
                if "document_id" not in doc.metadata:
                    doc.metadata["document_id"] = f"{self.collection_name}_{i}"
            
            # Add documents to vector store
            ids = self.vector_store.add_documents(documents)
            
            # Persist changes
            if hasattr(self.vector_store, "_persist"):
                self.vector_store._persist()
            
            return ids
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}")
            raise
    
    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Search for similar documents.
        
        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filter
            
        Returns:
            List of similar documents
        """
        try:
            return self.vector_store.similarity_search(
                query,
                k=k,
                filter=filter
            )
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return []
    
    def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """Get a document by its ID.
        
        Args:
            document_id: Document ID
            
        Returns:
            Document if found, None otherwise
        """
        try:
            results = self.vector_store.similarity_search(
                "",
                k=1,
                filter={"document_id": document_id}
            )
            if results and isinstance(results, list) and len(results) > 0:
                return results[0]
            return None
        except Exception as e:
            logger.error(f"Error getting document by ID: {str(e)}")
            return None
    
    def get_all_documents(self) -> List[Document]:
        """Get all documents in the collection.
        
        Returns:
            List of all documents
        """
        try:
            # This is a simple implementation that might not be efficient for large collections
            results = self.vector_store.similarity_search(
                "",
                k=1000  # Adjust based on your needs
            )
            if results and isinstance(results, list):
                return results
            return []
        except Exception as e:
            logger.error(f"Error getting all documents: {str(e)}")
            return []

    def delete_collection(self) -> bool:
        """Delete the collection.
        
        Returns:
            True if successful
        """
        try:
            if settings.VECTOR_DB_TYPE == "pinecone":
                pinecone.delete_index(self.collection_name)
            else:
                self.vector_store.delete_collection()
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {str(e)}")
            return False
    
    @staticmethod
    def chunk_document(text: str, metadata: Dict[str, Any] = None) -> List[Document]:
        """Split a document into chunks.
        
        Args:
            text: Document text
            metadata: Optional metadata
            
        Returns:
            List of document chunks
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            is_separator_regex=False,
        )
        
        docs = text_splitter.create_documents([text], [metadata or {}])
        return docs

    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        """Search for similar documents using semantic similarity.
        
        Args:
            query: The search query
            k: Number of results to return
            
        Returns:
            List of similar documents
        """
        try:
            # For Chroma, use similarity search
            if settings.VECTOR_DB_TYPE == "chroma":
                return self.vector_store.similarity_search(
                    query=query,
                    k=k
                )
            # For Pinecone, use similarity search
            else:
                return self.vector_store.similarity_search(
                    query=query,
                    k=k
                )
            
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return [] 