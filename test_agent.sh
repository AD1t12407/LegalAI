#!/bin/bash

# Create results directory if it doesn't exist
mkdir -p results

echo "Starting agent tests..."

# Test policy upload
echo "Testing policy upload..."
curl -X POST http://localhost:8000/api/policies/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_data/sample_policy.txt" \
  > results/policy_upload.json

# Test contract upload
echo "Testing contract upload..."
curl -X POST http://localhost:8000/api/contracts/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_data/sample_contract.txt" \
  -F "document_type=contract" \
  > results/contract_upload.json

# Get contract ID from the upload response
CONTRACT_ID=$(cat results/contract_upload.json | grep -o '"document_id":"[^"]*' | cut -d'"' -f4)

# Test clause extraction
echo "Testing clause extraction..."
curl -X GET "http://localhost:8000/api/contracts/${CONTRACT_ID}/clauses" \
  > results/clause_extraction.json

# Test risk assessment
echo "Testing risk assessment..."
curl -X GET "http://localhost:8000/api/contracts/${CONTRACT_ID}/risks" \
  > results/risk_assessment.json

# Test amendment suggestions
echo "Testing amendment suggestions..."
curl -X GET "http://localhost:8000/api/contracts/${CONTRACT_ID}/amendments" \
  > results/amendments.json

# Test summary generation
echo "Testing summary generation..."
curl -X GET "http://localhost:8000/api/contracts/${CONTRACT_ID}/summary" \
  > results/summary.json

# Test policy check
echo "Testing policy check..."
curl -X GET "http://localhost:8000/api/contracts/${CONTRACT_ID}/policy-check" \
  > results/policy_check.json

echo "All tests completed. Results stored in ./results directory" 