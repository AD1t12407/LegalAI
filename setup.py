#!/usr/bin/env python3
import os
import shutil
from pathlib import Path
import argparse

def setup_environment():
    """Set up the environment for ContractIQ."""
    print("Setting up ContractIQ environment...")
    
    # Create required directories
    dirs = [
        "data/contracts",
        "data/policies",
        "data/embeddings",
        "public/uploads"
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"Created directory: {dir_path}")
    
    # Create .env file if it doesn't exist
    if not os.path.exists(".env"):
        if os.path.exists("env.example"):
            shutil.copy("env.example", ".env")
            print("Created .env file from template.")
            print("⚠️ Please edit .env file to add your API keys!")
        else:
            print("⚠️ env.example not found. Please create a .env file manually.")
    else:
        print(".env file already exists.")
    
    print("\nSetup complete! 🎉")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Download spaCy model: python -m spacy download en_core_web_lg")
    print("3. Start the API server: uvicorn app.main:app --reload")
    print("4. Start the Streamlit frontend: streamlit run app/frontend/app.py")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ContractIQ Setup Script")
    parser.add_argument("--force", action="store_true", help="Force setup even if directories exist")
    
    args = parser.parse_args()
    
    if args.force:
        print("Forcing setup...")
    
    setup_environment() 