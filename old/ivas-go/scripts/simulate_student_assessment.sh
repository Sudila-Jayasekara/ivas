#!/bin/bash
# simulate_student_assessment.sh
# End-to-end test script for the assessment flow

set -e

BASE_URL="http://localhost:8080"
ASSIGNMENT_ID="assign-001"

echo "========================================="
echo "IVAS Phase 2 - Assessment Flow Test"
echo "========================================="

# 1. First, approve at least one question for the assignment
echo ""
echo "Step 0: Checking for approved questions..."
QUESTIONS=$(curl -s "$BASE_URL/api/v1/assignments/$ASSIGNMENT_ID/questions?status=approved")
QUESTION_COUNT=$(echo $QUESTIONS | jq '.data | length')

if [ "$QUESTION_COUNT" == "0" ] || [ "$QUESTION_COUNT" == "null" ]; then
    echo "No approved questions found. Please generate and approve questions first."
    echo "Run: POST /api/v1/assignments/assign-001/generate-questions"
    echo "Then: PUT /api/v1/questions/{id}/approve"
    exit 1
fi

echo "Found $QUESTION_COUNT approved questions"

# 2. Trigger assessment
echo ""
echo "Step 1: Triggering assessment..."
TRIGGER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/assessments/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "stud-001",
    "assignment_id": "assign-001",
    "task_id": "task-001",
    "code_context": "for i in range(10):\n    print(i)",
    "competencies": ["loops", "iteration"]
  }')

echo "$TRIGGER_RESPONSE" | jq .

SESSION_ID=$(echo $TRIGGER_RESPONSE | jq -r '.session_id')
QUESTION_INSTANCE_ID=$(echo $TRIGGER_RESPONSE | jq -r '.first_question.question_instance_id')

if [ "$SESSION_ID" == "null" ] || [ -z "$SESSION_ID" ]; then
    echo "Failed to create assessment session"
    exit 1
fi

echo "Session ID: $SESSION_ID"
echo "First Question Instance ID: $QUESTION_INSTANCE_ID"

# 3. Get session details
echo ""
echo "Step 2: Getting session details..."
curl -s "$BASE_URL/api/v1/assessments/sessions/$SESSION_ID" | jq .

# 4. Submit first response
echo ""
echo "Step 3: Submitting first response..."
RESPONSE1=$(curl -s -X POST "$BASE_URL/api/v1/assessments/sessions/$SESSION_ID/respond" \
  -H "Content-Type: application/json" \
  -d "{
    \"question_instance_id\": \"$QUESTION_INSTANCE_ID\",
    \"response_text\": \"A loop is a control structure that repeats a block of code. The for loop iterates from 0 to 9, printing each number.\",
    \"response_type\": \"text\"
  }")

echo "$RESPONSE1" | jq .

IS_COMPLETE=$(echo $RESPONSE1 | jq -r '.is_complete')
NEXT_QUESTION_INSTANCE_ID=$(echo $RESPONSE1 | jq -r '.next_question.question_instance_id')

# 5. Submit more responses until complete
RESPONSE_COUNT=1
while [ "$IS_COMPLETE" == "false" ] && [ "$RESPONSE_COUNT" -lt 5 ]; do
    if [ "$NEXT_QUESTION_INSTANCE_ID" == "null" ] || [ -z "$NEXT_QUESTION_INSTANCE_ID" ]; then
        echo "No more questions available"
        break
    fi
    
    RESPONSE_COUNT=$((RESPONSE_COUNT + 1))
    echo ""
    echo "Step 3.$RESPONSE_COUNT: Submitting response $RESPONSE_COUNT..."
    
    RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/assessments/sessions/$SESSION_ID/respond" \
      -H "Content-Type: application/json" \
      -d "{
        \"question_instance_id\": \"$NEXT_QUESTION_INSTANCE_ID\",
        \"response_text\": \"This is my response number $RESPONSE_COUNT to the assessment question.\",
        \"response_type\": \"text\"
      }")
    
    echo "$RESPONSE" | jq .
    
    IS_COMPLETE=$(echo $RESPONSE | jq -r '.is_complete')
    NEXT_QUESTION_INSTANCE_ID=$(echo $RESPONSE | jq -r '.next_question.question_instance_id')
done

# 6. Get final session state
echo ""
echo "Step 4: Getting final session state..."
curl -s "$BASE_URL/api/v1/assessments/sessions/$SESSION_ID" | jq .

# 7. Get transcript
echo ""
echo "Step 5: Getting assessment transcript..."
curl -s "$BASE_URL/api/v1/assessments/sessions/$SESSION_ID/transcript" | jq .

# 8. Get student sessions
echo ""
echo "Step 6: Getting all sessions for student..."
curl -s "$BASE_URL/api/v1/students/stud-001/sessions" | jq .

# 9. Get instructor view
echo ""
echo "Step 7: Getting instructor assessments..."
curl -s "$BASE_URL/api/v1/instructors/inst-001/assessments?assignment_id=assign-001" | jq .

echo ""
echo "========================================="
echo "Assessment Flow Test Complete!"
echo "========================================="
