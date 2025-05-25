import streamlit as st
import requests
import json
import os
from enum import Enum
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime

# API endpoint
API_URL = "http://localhost:8000"

# Document types
class DocumentType(str, Enum):
    CONTRACT = "contract"
    NDA = "nda"
    MSA = "msa"
    AGREEMENT = "agreement"
    POLICY = "policy"
    OTHER = "other"

# Risk levels
class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# Page setup
st.set_page_config(
    page_title="ContractIQ - Contract Analysis",
    page_icon="📝",
    layout="wide"
)

# Sidebar
st.sidebar.title("ContractIQ")
st.sidebar.caption("GenAI Contract Intelligence & Risk Review System")

# Navigation
page = st.sidebar.selectbox(
    "Navigation",
    ["Upload Contract", "Upload Policy", "View Contracts", "View Policies"]
)

# Helper functions
def upload_contract(file, document_type):
    """Upload a contract to the API."""
    files = {
        "file": (
            file.name,
            file.getvalue(),
            file.type if hasattr(file, 'type') else "application/octet-stream"
        )
    }
    data = {"document_type": document_type.value}
    response = requests.post(f"{API_URL}/api/contracts/upload", files=files, data=data)
    return response.json()

def upload_policy(file):
    """Upload a policy document to the API."""
    files = {"file": file}
    response = requests.post(f"{API_URL}/api/policies/upload", files=files)
    return response.json()

def analyze_contract(file_id, document_type):
    """Analyze a contract using the API."""
    response = requests.post(
        f"{API_URL}/api/contracts/analyze/{file_id}",
        params={"document_type": document_type}
    )
    return response.json()

def get_policies():
    """Get list of policies from the API."""
    response = requests.get(f"{API_URL}/api/policies/")
    return response.json().get("policies", [])

def format_risk_level(risk_level):
    """Format risk level with color."""
    if risk_level == "high":
        return "🔴 HIGH"
    elif risk_level == "medium":
        return "🟠 MEDIUM"
    else:
        return "🟢 LOW"

# Pages
if page == "Upload Contract":
    st.title("Upload Contract")
    
    with st.form("upload_contract_form"):
        uploaded_file = st.file_uploader("Choose a contract file", type=["pdf", "txt", "docx"])
        document_type = st.selectbox("Document Type", [t for t in DocumentType if t != DocumentType.POLICY])
        analyze_now = st.checkbox("Analyze immediately", value=True)
        submit_button = st.form_submit_button("Upload")
        
        if submit_button and uploaded_file is not None:
            with st.spinner("Uploading contract..."):
                try:
                    # Upload contract
                    response = upload_contract(uploaded_file, document_type)
                    st.success(f"Contract uploaded successfully! File ID: {response['file_id']}")
                    
                    # Analyze contract if requested
                    if analyze_now:
                        with st.spinner("Analyzing contract... This may take a minute."):
                            try:
                                analysis = analyze_contract(response['file_id'], document_type)
                                
                                # Display analysis
                                st.subheader("Contract Analysis")
                                
                                # Basic info
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Overall Risk Level", format_risk_level(analysis['overall_risk_level']))
                                col2.metric("Risk Score", f"{analysis['overall_risk_score']:.2f}")
                                col3.metric("Clauses Analyzed", len(analysis['clauses']))
                                
                                # Summary
                                st.subheader("Executive Summary")
                                st.write(analysis['summary'])
                                
                                # Recommendations
                                st.subheader("Recommendations")
                                for rec in analysis['recommendations']:
                                    st.write(f"• {rec}")
                                
                                # Risk assessments
                                st.subheader("Clause Risk Assessment")
                                
                                # Create a DataFrame for the clauses
                                clause_data = []
                                for clause in analysis['clauses']:
                                    # Find corresponding risk assessment
                                    risk = next((r for r in analysis['risk_assessments'] 
                                                if r['clause_id'] == clause['clause_id']), None)
                                    
                                    if risk:
                                        clause_data.append({
                                            "Type": clause['clause_type'].capitalize(),
                                            "Risk Level": risk['risk_level'].upper(),
                                            "Risk Score": f"{risk['risk_score']:.2f}",
                                            "Text": clause['text'][:100] + "..." if len(clause['text']) > 100 else clause['text']
                                        })
                                
                                # Display as a table
                                if clause_data:
                                    df = pd.DataFrame(clause_data)
                                    st.dataframe(df)
                                else:
                                    st.info("No clauses found in the contract.")
                                
                            except Exception as e:
                                st.error(f"Error analyzing contract: {str(e)}")
                    
                except Exception as e:
                    st.error(f"Error uploading contract: {str(e)}")

elif page == "Upload Policy":
    st.title("Upload Policy Document")
    
    with st.form("upload_policy_form"):
        uploaded_file = st.file_uploader("Choose a policy document", type=["pdf", "txt", "docx"])
        submit_button = st.form_submit_button("Upload")
        
        if submit_button and uploaded_file is not None:
            with st.spinner("Uploading policy document..."):
                try:
                    response = upload_policy(uploaded_file)
                    st.success(f"Policy document uploaded successfully! File ID: {response['file_id']}")
                except Exception as e:
                    st.error(f"Error uploading policy document: {str(e)}")

elif page == "View Contracts":
    st.title("View Contracts")
    st.info("This feature is not yet implemented.")
    
    # Placeholder for contract list
    st.subheader("Contract List")
    st.write("No contracts found. Please upload a contract first.")

elif page == "View Policies":
    st.title("View Policies")
    
    # Refresh button
    if st.button("Refresh Policy List"):
        st.experimental_rerun()
    
    # Get policies
    try:
        policies = get_policies()
        
        if policies:
            # Create a DataFrame
            policy_data = []
            for policy in policies:
                policy_data.append({
                    "ID": policy['file_id'],
                    "Filename": policy['filename'],
                    "Size (KB)": f"{policy['size'] / 1024:.1f}",
                    "Upload Date": datetime.fromtimestamp(policy['upload_date']).strftime('%Y-%m-%d %H:%M')
                })
            
            # Display as a table
            df = pd.DataFrame(policy_data)
            st.dataframe(df)
        else:
            st.info("No policy documents found. Please upload a policy document first.")
    
    except Exception as e:
        st.error(f"Error retrieving policies: {str(e)}")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("© 2023 ContractIQ") 