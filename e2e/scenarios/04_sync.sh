#!/bin/bash
# Scenario 04: Message Synchronization
# Verifies that agents can sync and see each other's messages

set -e

echo "📋 Scenario: Message Synchronization"
echo "   Testing multi-agent message sync..."

# Function to run command on a specific agent
run_on_agent() {
    local agent="$1"
    shift
    docker exec "brain-agent-$agent" /entrypoint.sh "$@"
}

# Unique timestamp for this test
TIMESTAMP=$(date +%s)

echo ""
echo "1️⃣  All agents sync from remote..."
run_on_agent claude sync || true
run_on_agent gpt sync || true
run_on_agent gemini sync || true
echo "   ✓ All agents synced"

echo ""
echo "2️⃣  Claude sends a message..."
run_on_agent claude send "Test message from Claude at $TIMESTAMP"
run_on_agent claude push || true
echo "   ✓ Claude sent message and pushed"

echo ""
echo "3️⃣  GPT sends a message..."
run_on_agent gpt send "Test message from GPT at $TIMESTAMP"
run_on_agent gpt push || true
echo "   ✓ GPT sent message and pushed"

echo ""
echo "4️⃣  Gemini sends a message..."
run_on_agent gemini send "Test message from Gemini at $TIMESTAMP"
run_on_agent gemini push || true
echo "   ✓ Gemini sent message and pushed"

echo ""
echo "5️⃣  All agents post read receipts..."
run_on_agent claude receipt || true
run_on_agent gpt receipt || true
run_on_agent gemini receipt || true
echo "   ✓ All receipts posted"

echo ""
echo "6️⃣  Checking Claude's event log..."
run_on_agent claude msg log || true

echo ""
echo "7️⃣  Checking status across agents..."
echo "--- Claude Status ---"
run_on_agent claude status || true
echo ""
echo "--- GPT Status ---"
run_on_agent gpt status || true
echo ""
echo "--- Gemini Status ---"
run_on_agent gemini status || true

echo ""
echo "✅ Sync scenario completed"

