# E2E Testing with Docker Compose

This directory contains end-to-end tests for the Brain Protocol using Docker Compose to simulate 3 independent agent instances.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Network                               │
│                                                                  │
│  ┌──────────────┐                                               │
│  │  git-server  │  Bare git repo (simulates GitHub)             │
│  │  /repo       │                                               │
│  └──────┬───────┘                                               │
│         │ (volume: shared-repo)                                 │
│         │                                                       │
│  ┌──────┴───────┬──────────────┬──────────────┐                │
│  │              │              │              │                │
│  ▼              ▼              ▼              ▼                │
│ ┌────────┐  ┌────────┐  ┌────────┐  ┌─────────────┐           │
│ │ claude │  │  gpt   │  │ gemini │  │ test-runner │           │
│ │  🟠    │  │  🟢    │  │  🔵    │  │     🧪      │           │
│ └────────┘  └────────┘  └────────┘  └─────────────┘           │
│                                                                  │
│ Each agent has its own:                                         │
│  - Workspace (cloned repo)                                      │
│  - Identity (.brain/self.json)                                  │
│  - Message history                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Start all agents (background)
docker compose -f docker-compose.e2e.yml up -d --build

# Run e2e tests
docker compose -f docker-compose.e2e.yml --profile test run test-runner

# Interactive access to an agent
docker compose -f docker-compose.e2e.yml exec claude /entrypoint.sh shell

# View logs
docker compose -f docker-compose.e2e.yml logs -f

# Clean up
docker compose -f docker-compose.e2e.yml down -v
```

## Manual Testing

```bash
# Start agents
docker compose -f docker-compose.e2e.yml up -d

# Send message from Claude
docker exec brain-agent-claude /entrypoint.sh send "Hello from Claude!"

# Check GPT's status
docker exec brain-agent-gpt /entrypoint.sh status

# Have Gemini listen for announcements
docker exec brain-agent-gemini /entrypoint.sh listen

# Make Claude claim a phase
docker exec brain-agent-claude /entrypoint.sh claim 42
```

## Test Scenarios

| Scenario | File | Description |
|----------|------|-------------|
| Identity | `01_identity.sh` | Verifies unique identities for each agent |
| Announcements | `02_announcements.sh` | Tests cross-branch announcement system |
| Claims | `03_claims.sh` | Tests phase claiming mechanism |
| Sync | `04_sync.sh` | Tests message synchronization |

## Troubleshooting

### Agents not starting
```bash
docker compose -f docker-compose.e2e.yml logs git-server
docker compose -f docker-compose.e2e.yml logs claude
```

### Reset everything
```bash
docker compose -f docker-compose.e2e.yml down -v
docker volume prune -f
```

### Access agent shell
```bash
docker exec -it brain-agent-claude /bin/bash
```

