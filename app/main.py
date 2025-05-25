from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import logging
import os

from app.api import contracts, policies, analysis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create required directories if they don't exist
os.makedirs("data/contracts", exist_ok=True)
os.makedirs("data/policies", exist_ok=True)
os.makedirs("data/embeddings", exist_ok=True)
os.makedirs("public/uploads", exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title="ContractIQ API",
    description="GenAI Contract Intelligence & Risk Review System",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="public"), name="static")

# Include API routers
app.include_router(contracts.router, prefix="/api/contracts", tags=["contracts"])
app.include_router(policies.router, prefix="/api/policies", tags=["policies"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])

@app.get("/", tags=["root"])
async def read_root():
    """Root endpoint providing API information."""
    return {
        "app": "ContractIQ",
        "description": "GenAI Contract Intelligence & Risk Review System",
        "version": "1.0.0",
        "status": "operational"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 