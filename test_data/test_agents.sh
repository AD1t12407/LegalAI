#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Create directories
mkdir -p results/{run1,run2,run3}/{clauses,policies,risks,amendments,summaries}

# Function to run a complete analysis cycle
run_analysis() {
    RUN_NUMBER=$1
    echo -e "${GREEN}Starting Analysis Run #${RUN_NUMBER}${NC}\n"
    
    # First upload the policy document
    echo -e "${YELLOW}Uploading Policy Document...${NC}"
    echo "Uploading file: test_data/test_policy.txt"
    POLICY_RESPONSE=$(curl -v -X POST http://localhost:8005/api/policies/upload \
      -H "Content-Type: multipart/form-data" \
      -F "file=@test_data/test_policy.txt" \
      -F "document_type=policy")
    echo "Policy upload response: $POLICY_RESPONSE"
    echo $POLICY_RESPONSE > "results/run${RUN_NUMBER}/policy_upload.json"
    echo -e "\n"
    
    # Function to analyze a contract with all agents
    analyze_contract() {
        CONTRACT_FILE=$1
        RISK_LEVEL=$2
        RISK_LEVEL_LOWER=$(echo "$RISK_LEVEL" | tr '[:upper:]' '[:lower:]')
        
        echo -e "${YELLOW}Testing $RISK_LEVEL Risk Contract${NC}"
        
        # 1. Document Ingestion
        echo "1. Uploading contract..."
        echo "Uploading file: test_data/contracts/$CONTRACT_FILE"
        UPLOAD_RESPONSE=$(curl -v -X POST http://localhost:8005/api/contracts/upload \
          -H "Content-Type: multipart/form-data" \
          -F "file=@test_data/contracts/$CONTRACT_FILE" \
          -F "document_type=contract")
        echo "Contract upload response: $UPLOAD_RESPONSE"
        echo $UPLOAD_RESPONSE > "results/run${RUN_NUMBER}/${RISK_LEVEL_LOWER}_upload.json"
        
        # Extract contract ID and debug
        echo "Upload response: $UPLOAD_RESPONSE"
        CONTRACT_ID=$(echo $UPLOAD_RESPONSE | jq -r '.file_id // empty')
        if [ -z "$CONTRACT_ID" ]; then
            CONTRACT_ID=$(echo $UPLOAD_RESPONSE | jq -r '.document_id // empty')
        fi
        echo "Contract ID: $CONTRACT_ID"
        
        if [ -z "$CONTRACT_ID" ]; then
            echo -e "${RED}Failed to extract contract ID from response${NC}"
            return 1
        fi
        
        # 2. Clause Extraction
        echo "2. Extracting clauses..."
        CLAUSES_RESPONSE=$(curl -s -X GET "http://localhost:8005/api/contracts/${CONTRACT_ID}/clauses" \
          -H "Content-Type: application/json")
        echo "Clauses response: $CLAUSES_RESPONSE"
        echo $CLAUSES_RESPONSE > "results/run${RUN_NUMBER}/clauses/${RISK_LEVEL_LOWER}_clauses.json"
        
        # 3. Policy Check
        echo "3. Checking against policies..."
        POLICY_CHECK_RESPONSE=$(curl -s -X GET "http://localhost:8005/api/analysis/${CONTRACT_ID}/policy-check" \
          -H "Content-Type: application/json")
        echo "Policy check response: $POLICY_CHECK_RESPONSE"
        echo $POLICY_CHECK_RESPONSE > "results/run${RUN_NUMBER}/policies/${RISK_LEVEL_LOWER}_policy_check.json"
        
        # 4. Risk Assessment
        echo "4. Assessing risks..."
        RISK_RESPONSE=$(curl -s -X GET "http://localhost:8005/api/analysis/${CONTRACT_ID}/risks" \
          -H "Content-Type: application/json")
        echo "Risk assessment response: $RISK_RESPONSE"
        echo $RISK_RESPONSE > "results/run${RUN_NUMBER}/risks/${RISK_LEVEL_LOWER}_risks.json"
        
        # Extract risk metrics with debug
        echo "Risk response: $RISK_RESPONSE"
        RISK_SCORE=$(echo $RISK_RESPONSE | jq -r '.overall_risk_score // empty')
        RISK_LEVEL_RESULT=$(echo $RISK_RESPONSE | jq -r '.overall_risk_level // empty')
        echo "Extracted risk score: $RISK_SCORE"
        echo "Extracted risk level: $RISK_LEVEL_RESULT"
        
        # 5. Amendment Suggestions
        echo "5. Generating amendment suggestions..."
        AMENDMENTS_RESPONSE=$(curl -s -X GET "http://localhost:8005/api/analysis/${CONTRACT_ID}/amendments" \
          -H "Content-Type: application/json")
        echo "Amendments response: $AMENDMENTS_RESPONSE"
        echo $AMENDMENTS_RESPONSE > "results/run${RUN_NUMBER}/amendments/${RISK_LEVEL_LOWER}_amendments.json"
        
        # 6. Summary Generation
        echo "6. Generating summary..."
        SUMMARY_RESPONSE=$(curl -s -X GET "http://localhost:8005/api/analysis/${CONTRACT_ID}/summary" \
          -H "Content-Type: application/json")
        echo "Summary response: $SUMMARY_RESPONSE"
        echo $SUMMARY_RESPONSE > "results/run${RUN_NUMBER}/summaries/${RISK_LEVEL_LOWER}_summary.json"
        
        echo -e "\nResults for ${RISK_LEVEL} Risk Contract:"
        echo -e "Risk Score: ${RED}$RISK_SCORE${NC}"
        echo -e "Risk Level: ${RED}$RISK_LEVEL_RESULT${NC}"
        echo -e "Results saved in results/run${RUN_NUMBER}/${RISK_LEVEL_LOWER}_*.json\n"
    }
    
    # Analyze each contract
    analyze_contract "high_risk_contract.txt" "High"
    analyze_contract "medium_risk_contract.txt" "Medium"
    analyze_contract "low_risk_contract.txt" "Low"
    
    # Get overall statistics
    echo -e "${YELLOW}Getting Overall Statistics...${NC}"
    STATS_RESPONSE=$(curl -s -X GET http://localhost:8005/api/analysis/stats)
    echo "Stats response: $STATS_RESPONSE"
    echo $STATS_RESPONSE > "results/run${RUN_NUMBER}/analysis_stats.json"
    echo -e "Statistics saved to results/run${RUN_NUMBER}/analysis_stats.json\n"
    
    echo -e "${GREEN}Analysis Run #${RUN_NUMBER} Complete!${NC}\n"
}

# Run three complete analysis cycles
for run in {1..3}; do
    run_analysis $run
    if [ $run -lt 3 ]; then
        echo -e "${YELLOW}Waiting 5 seconds before next run...${NC}\n"
        sleep 5
    fi
done

# Compare results across runs
echo -e "${GREEN}Comparing Results Across Runs${NC}"
for risk_level in high medium low; do
    echo -e "\n${YELLOW}Comparing ${risk_level} risk contract results:${NC}"
    for run in {1..3}; do
        RISK_SCORE=$(jq -r '.overall_risk_score // empty' "results/run${run}/risks/${risk_level}_risks.json")
        echo -e "Run ${run} Risk Score: ${RED}$RISK_SCORE${NC}"
    done
done

echo -e "\n${GREEN}All Tests Complete!${NC}" 