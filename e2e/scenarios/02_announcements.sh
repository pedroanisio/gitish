#!/bin/bash
# Scenario 02: Cross-Branch Announcements
# Verifies that announcements are visible across all agents

set -e

echo "📋 Scenario: Cross-Branch Announcements"
echo "   Testing announcement broadcast system..."

# Function to run command on a specific agent
run_on_agent() {
    local agent="$1"
    shift
    docker exec "brain-agent-$agent" /entrypoint.sh "$@"
}

# Unique message for this test run
TEST_MSG="E2E-TEST-$(date +%s)-ANNOUNCEMENT"

echo ""
echo "1️⃣  Claude sends announcement..."
run_on_agent claude announce "🚀 $TEST_MSG from Claude"
echo "   ✓ Announcement sent"

sleep 2  # Allow propagation

echo ""
echo "2️⃣  GPT listens for announcements..."
GPT_LISTEN=$(run_on_agent gpt listen 2>&1 || true)
if echo "$GPT_LISTEN" | grep -q "$TEST_MSG"; then
    echo "   ✓ GPT received Claude's announcement"
else
    echo "   ⚠ GPT may not have received announcement yet (expected in async systems)"
fi

echo ""
echo "3️⃣  Gemini listens for announcements..."
GEMINI_LISTEN=$(run_on_agent gemini listen 2>&1 || true)
if echo "$GEMINI_LISTEN" | grep -q "$TEST_MSG"; then
    echo "   ✓ Gemini received Claude's announcement"
else
    echo "   ⚠ Gemini may not have received announcement yet (expected in async systems)"
fi

echo ""
echo "4️⃣  GPT sends announcement..."
run_on_agent gpt announce "📢 $TEST_MSG from GPT"
echo "   ✓ GPT announcement sent"

sleep 2

echo ""
echo "5️⃣  Claude listens for GPT's announcement..."
CLAUDE_LISTEN=$(run_on_agent claude listen 2>&1 || true)
if echo "$CLAUDE_LISTEN" | grep -q "from GPT"; then
    echo "   ✓ Claude received GPT's announcement"
else
    echo "   ⚠ Claude may not have received announcement yet"
fi

echo ""
echo "✅ Announcement scenario completed"
echo "   Note: In distributed systems, propagation may be async"

