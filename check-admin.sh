#!/bin/bash
# Check Admin Setup - Diagnostic Script

echo "==================================="
echo "RTI4All Admin Setup Diagnostic"
echo "==================================="
echo ""

# Check if .env file exists
if [ -f .env ]; then
    echo "✓ .env file exists"

    # Check for ADMIN_EMAILS
    if grep -q "ADMIN_EMAILS=" .env; then
        ADMIN_EMAILS=$(grep "ADMIN_EMAILS=" .env | cut -d '=' -f2)
        echo "✓ ADMIN_EMAILS found: $ADMIN_EMAILS"

        # Check if officer@gov.mv is in the list
        if echo "$ADMIN_EMAILS" | grep -qi "officer@gov.mv"; then
            echo "✓ officer@gov.mv is in ADMIN_EMAILS"
        else
            echo "✗ officer@gov.mv is NOT in ADMIN_EMAILS"
            echo "  Add it to .env: ADMIN_EMAILS=officer@gov.mv"
        fi
    else
        echo "✗ ADMIN_EMAILS not found in .env"
        echo "  Add this line to .env: ADMIN_EMAILS=officer@gov.mv"
    fi
else
    echo "✗ .env file not found"
    echo "  Run: cp .env.example .env"
fi

echo ""
echo "==================================="
echo "Backend Status"
echo "==================================="

# Check if backend container is running
if docker ps | grep -q "rti4all-backend"; then
    echo "✓ Backend container is running"

    # Check backend logs for ADMIN_EMAILS
    echo ""
    echo "Checking backend environment..."
    docker exec rti4all-backend printenv | grep ADMIN_EMAILS || echo "✗ ADMIN_EMAILS not set in backend container"
else
    echo "✗ Backend container is not running"
    echo "  Run: docker compose up"
fi

echo ""
echo "==================================="
echo "Next Steps"
echo "==================================="
echo ""
echo "If officer@gov.mv was created BEFORE setting ADMIN_EMAILS:"
echo "1. Ensure .env has: ADMIN_EMAILS=officer@gov.mv"
echo "2. Restart backend: docker compose restart backend"
echo "3. Log out from the frontend"
echo "4. Log back in - retrofit will activate"
echo ""
echo "OR start fresh:"
echo "1. docker compose down"
echo "2. docker compose up"
echo "3. Sign up again with officer@gov.mv"
echo ""
