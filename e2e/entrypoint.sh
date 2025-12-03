#!/bin/bash
# Entrypoint for Brain Protocol Agent containers
# Initializes git, clones repo, sets up identity

set -e

AGENT_NAME="${AGENT_NAME:-agent}"
GIT_REMOTE="${GIT_REMOTE:-/shared-repo}"
WORKSPACE="${WORKSPACE:-/workspace/repo}"

echo "🤖 Agent: $AGENT_NAME starting..."

# Configure git identity
git config --global user.name "$AGENT_NAME"
git config --global user.email "$AGENT_NAME@brain.local"
git config --global init.defaultBranch main
git config --global pull.rebase false

# Wait for shared repo to be ready
wait_for_repo() {
    local max_wait=30
    local count=0
    while [ ! -d "$GIT_REMOTE/objects" ]; do
        echo "⏳ Waiting for shared repo at $GIT_REMOTE..."
        sleep 1
        count=$((count + 1))
        if [ $count -ge $max_wait ]; then
            echo "❌ Timeout waiting for shared repo"
            exit 1
        fi
    done
    echo "✅ Shared repo ready"
}

# Clone or initialize the workspace
setup_workspace() {
    mkdir -p "$WORKSPACE"
    cd "$WORKSPACE"
    
    if [ -d ".git" ]; then
        echo "📂 Workspace exists, pulling latest..."
        git fetch origin --all 2>/dev/null || true
        git pull origin main 2>/dev/null || true
    else
        echo "📥 Cloning shared repo..."
        # Check if remote repo has any commits
        if git ls-remote "$GIT_REMOTE" HEAD 2>/dev/null | grep -q HEAD; then
            git clone "$GIT_REMOTE" .
        else
            echo "📦 Remote is empty, initializing new repo..."
            git init
            git remote add origin "$GIT_REMOTE"
        fi
    fi
    
    # Create package.json if not exists (required by brain)
    if [ ! -f "package.json" ]; then
        echo '{"name": "brain-e2e-test"}' > package.json
        git add package.json
        git commit -m "init: add package.json" 2>/dev/null || true
        git push -u origin main 2>/dev/null || true
    fi
    
    echo "✅ Workspace ready at $WORKSPACE"
}

# Initialize brain identity
init_identity() {
    cd "$WORKSPACE"
    echo "🧠 Initializing brain identity for $AGENT_NAME..."
    python -m brain.cli init --name "$AGENT_NAME" 2>/dev/null || true
}

# Run a brain command
run_brain() {
    cd "$WORKSPACE"
    python -m brain.cli "$@"
}

# Main logic based on command
case "${1:-idle}" in
    init)
        wait_for_repo
        setup_workspace
        init_identity
        echo "✅ Agent $AGENT_NAME initialized"
        ;;
    
    sync)
        cd "$WORKSPACE"
        run_brain sync
        run_brain receipt
        ;;
    
    send)
        shift
        cd "$WORKSPACE"
        run_brain msg send "$@"
        ;;
    
    announce)
        shift
        cd "$WORKSPACE"
        run_brain msg announce "$@"
        ;;
    
    listen)
        cd "$WORKSPACE"
        run_brain msg listen
        ;;
    
    claim)
        shift
        cd "$WORKSPACE"
        run_brain phase claim "$@"
        ;;
    
    status)
        cd "$WORKSPACE"
        run_brain status
        ;;
    
    push)
        cd "$WORKSPACE"
        git push origin HEAD || true
        ;;
    
    pull)
        cd "$WORKSPACE"
        git fetch origin --all
        git pull origin main || true
        ;;
    
    shell)
        cd "$WORKSPACE"
        exec /bin/bash
        ;;
    
    idle)
        wait_for_repo
        setup_workspace
        init_identity
        echo "✅ Agent $AGENT_NAME ready. Idling..."
        # Keep container running
        tail -f /dev/null
        ;;
    
    test)
        shift
        wait_for_repo
        setup_workspace
        init_identity
        echo "🧪 Running test scenario: $@"
        exec "$@"
        ;;
    
    *)
        # Pass through to brain CLI
        cd "$WORKSPACE"
        run_brain "$@"
        ;;
esac

