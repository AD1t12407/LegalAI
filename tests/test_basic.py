import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_read_root():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["app"] == "ContractIQ"
    assert "version" in response.json()

def test_api_structure():
    """Test that the API structure is correct."""
    # Test OpenAPI schema
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    
    # Check that the main endpoints are defined
    assert "/api/contracts/upload" in schema["paths"]
    assert "/api/policies/upload" in schema["paths"]
    assert "/api/analysis/stats" in schema["paths"] 