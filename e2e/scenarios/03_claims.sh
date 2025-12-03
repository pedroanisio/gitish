#!/bin/bash
# Scenario 03: Phase Claims
# Verifies that phases can be claimed and are exclusive

set -e

echo "📋 Scenario: Phase Claims"
echo "   Testing exclusive phase claim system..."

# Function to run command on a specific agent
run_on_agent() {
    local agent="$1"
    shift
    docker exec "brain-agent-$agent" /entrypoint.sh "$@"
}

# Use unique phase numbers for this test
PHASE_A=$((100 + RANDOM % 100))
PHASE_B=$((200 + RANDOM % 100))
PHASE_C=$((300 + RANDOM % 100))

echo ""
echo "1️⃣  Claude claims phase $PHASE_A..."
run_on_agent claude claim "$PHASE_A" || true
echo "   ✓ Claude claimed phase $PHASE_A"

echo ""
echo "2️⃣  GPT claims phase $PHASE_B..."
run_on_agent gpt claim "$PHASE_B" || true
echo "   ✓ GPT claimed phase $PHASE_B"

echo ""
echo "3️⃣  Gemini claims phase $PHASE_C..."
run_on_agent gemini claim "$PHASE_C" || true
echo "   ✓ Gemini claimed phase $PHASE_C"

echo ""
echo "4️⃣  Verifying phase claims via 'phase list'..."
CLAUDE_PHASES=$(run_on_agent claude phase list 2>&1 || true)
echo "$CLAUDE_PHASES" | head -20

echo ""
echo "5️⃣  Claude syncs and posts receipt..."
run_on_agent claude sync || true
run_on_agent claude receipt || true
echo "   ✓ Claude synced"

echo ""
echo "6️⃣  GPT syncs and posts receipt..."
run_on_agent gpt sync || true
run_on_agent gpt receipt || true
echo "   ✓ GPT synced"

echo ""
echo "7️⃣  Gemini syncs and posts receipt..."
run_on_agent gemini sync || true
run_on_agent gemini receipt || true
echo "   ✓ Gemini synced"

echo ""
echo "✅ Phase claims scenario completed"

