import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Disable tokenizers parallelism to avoid forking warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Data directories
CONTRACTS_DIR = BASE_DIR / "data" / "contracts"
POLICIES_DIR = BASE_DIR / "data" / "policies"
EMBEDDINGS_DIR = BASE_DIR / "data" / "embeddings"
UPLOADS_DIR = BASE_DIR / "public" / "uploads"

# Ensure directories exist
CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
POLICIES_DIR.mkdir(parents=True, exist_ok=True)
EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    """Application settings."""
    
    # App settings
    APP_NAME: str = "ContractIQ"
    API_VERSION: str = "1.0.0"
    
    # Groq settings
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # LLM settings
    DEFAULT_MODEL: str = "llama3-70b-8192"
    LLM_MODEL: str = "llama3-70b-8192"
    
    # Document processing settings
    MAX_TOKEN_LIMIT: int = 8192
    CHUNK_SIZE: int = 2000
    CHUNK_OVERLAP: int = 400
    
    # Vector database settings
    VECTOR_STORE_DIR: str = "vector_store"
    VECTOR_DB_TYPE: str = "chroma"
    
    # Embeddings settings
    EMBEDDING_MODEL: str = "sentence-transformers/all-mpnet-base-v2"
    
    # Paths
    CONTRACTS_DIR: Path = CONTRACTS_DIR
    POLICIES_DIR: Path = POLICIES_DIR
    EMBEDDINGS_DIR: Path = EMBEDDINGS_DIR
    UPLOADS_DIR: Path = UPLOADS_DIR
    
    # Clause types to extract
    CLAUSE_TYPES: list = [
        "termination",
        "jurisdiction",
        "payment_terms",
        "confidentiality",
        "intellectual_property",
        "liability",
        "indemnification",
        "force_majeure",
        "assignment",
        "governing_law",
    ]
    
    # Risk scoring thresholds
    RISK_HIGH_THRESHOLD: float = 0.7
    RISK_MEDIUM_THRESHOLD: float = 0.4
    
    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"

# Create settings instance
settings = Settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",) 