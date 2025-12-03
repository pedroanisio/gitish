#!/bin/bash
# Scenario 01: Multi-Agent Identity Verification
# Verifies that 3 agents can independently create and maintain identities

set -e

echo "📋 Scenario: Multi-Agent Identity"
echo "   Verifying independent agent identities..."

# Function to run command on a specific agent
run_on_agent() {
    local agent="$1"
    shift
    docker exec "brain-agent-$agent" /entrypoint.sh "$@"
}

# Check each agent's identity
echo ""
echo "1️⃣  Checking Claude's identity..."
run_on_agent claude status | grep -q "claude" && echo "   ✓ Claude identity exists"

echo ""
echo "2️⃣  Checking GPT's identity..."
run_on_agent gpt status | grep -q "gpt" && echo "   ✓ GPT identity exists"

echo ""
echo "3️⃣  Checking Gemini's identity..."
run_on_agent gemini status | grep -q "gemini" && echo "   ✓ Gemini identity exists"

# Verify identities are unique
echo ""
echo "4️⃣  Verifying identities are unique..."

CLAUDE_ID=$(run_on_agent claude status 2>/dev/null | grep "Full ID" | awk '{print $NF}' || echo "")
GPT_ID=$(run_on_agent gpt status 2>/dev/null | grep "Full ID" | awk '{print $NF}' || echo "")
GEMINI_ID=$(run_on_agent gemini status 2>/dev/null | grep "Full ID" | awk '{print $NF}' || echo "")

if [ "$CLAUDE_ID" != "$GPT_ID" ] && [ "$GPT_ID" != "$GEMINI_ID" ] && [ "$CLAUDE_ID" != "$GEMINI_ID" ]; then
    echo "   ✓ All identities are unique"
    echo "     Claude: $CLAUDE_ID"
    echo "     GPT: $GPT_ID"
    echo "     Gemini: $GEMINI_ID"
else
    echo "   ✗ Identity collision detected!"
    exit 1
fi

echo ""
echo "✅ Identity scenario passed"

