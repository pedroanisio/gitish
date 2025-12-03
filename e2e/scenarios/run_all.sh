#!/bin/bash
# E2E Test Runner - Orchestrates all test scenarios
# Run from test-runner container

set -e

SCENARIOS_DIR="/workspace/e2e/scenarios"
PASSED=0
FAILED=0

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Brain Protocol E2E Test Suite                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

run_scenario() {
    local name="$1"
    local script="$2"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 Running: $name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if bash "$script"; then
        echo "✅ PASSED: $name"
        PASSED=$((PASSED + 1))
    else
        echo "❌ FAILED: $name"
        FAILED=$((FAILED + 1))
    fi
    echo ""
}

# Initialize test environment
echo "🔧 Initializing test environment..."
cd /workspace/repo

# Ensure we have an identity
python -m brain.cli init --name test-runner 2>/dev/null || true

# Run scenarios
run_scenario "Multi-Agent Identity" "$SCENARIOS_DIR/01_identity.sh"
run_scenario "Cross-Branch Announcements" "$SCENARIOS_DIR/02_announcements.sh"
run_scenario "Phase Claims" "$SCENARIOS_DIR/03_claims.sh"
run_scenario "Message Synchronization" "$SCENARIOS_DIR/04_sync.sh"

# Summary
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                      Test Summary                                 ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  ✅ Passed: $PASSED                                                    ║"
echo "║  ❌ Failed: $FAILED                                                    ║"
echo "╚══════════════════════════════════════════════════════════════════╝"

if [ $FAILED -gt 0 ]; then
    exit 1
fi

echo "🎉 All tests passed!"
exit 0

