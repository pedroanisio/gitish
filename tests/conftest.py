"""
Pytest configuration and fixtures for Brain Protocol tests.

Updated for unified brain/ package (v2.0).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest


# Add src directory to path for brain package imports
SRC_DIR = Path(__file__).parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture
def temp_repo() -> Generator[Path, None, None]:
    """
    Create a temporary git repository for testing.
    Yields the path to the repo root.
    Cleans up after test.
    """
    original_cwd = os.getcwd()
    temp_dir = tempfile.mkdtemp(prefix="brain_test_")
    temp_path = Path(temp_dir)

    try:
        os.chdir(temp_path)

        # Initialize git repo
        subprocess.run(["git", "init"], check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            check=True, capture_output=True
        )
        # Disable commit signing for tests
        subprocess.run(
            ["git", "config", "commit.gpgsign", "false"],
            check=True, capture_output=True
        )

        # Create minimal package.json (required by brain)
        (temp_path / "package.json").write_text('{"name": "test"}')

        # Create docs dir with PHASE-CLAIMS.md
        (temp_path / "docs").mkdir()
        (temp_path / "docs" / "PHASE-CLAIMS.md").write_text("""# Phase Claims Registry

| Phase | Description | Status | Claimed By | Branch | Started | PR |
|-------|-------------|--------|------------|--------|---------|-----|
| 5 | Core Enums | AVAILABLE | - | - | - | - |
| 7 | Common Types | AVAILABLE | - | - | - | - |
| 11 | Validation | IN_PROGRESS | @claude | claude/phase-11 | 2025-12-03 | - |
| 12 | Factories | COMPLETE | @bob | bob/phase-12 | 2025-12-01 | #42 |
| 15 | Config | BLOCKED | - | - | - | - |
""")

        # Initial commit
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            check=True, capture_output=True
        )

        yield temp_path

    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# Legacy fixtures (for backward compatibility with old brain.py tests)
# =============================================================================

@pytest.fixture
def brain_module(temp_repo: Path):
    """
    Import brain.py module dynamically for testing.
    DEPRECATED: Use brain_core, brain_identity, etc. fixtures instead.
    """
    import importlib.util

    # Get path to brain.py (in src/brain/)
    brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain.py"

    spec = importlib.util.spec_from_file_location("brain_legacy", brain_path)
    brain = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(brain)

    return brain


@pytest.fixture
def mission_module(temp_repo: Path):
    """
    Import missions module for testing.
    DEPRECATED: Use brain_missions fixture instead.
    """
    from brain import missions
    return missions


# =============================================================================
# New unified brain/ package fixtures
# =============================================================================

@pytest.fixture
def brain_core(temp_repo: Path):
    """Import brain.core module for testing."""
    from brain import core
    return core


@pytest.fixture
def brain_identity(temp_repo: Path):
    """Import brain.identity module for testing."""
    from brain import identity
    return identity


@pytest.fixture
def brain_messaging(temp_repo: Path):
    """Import brain.messaging module for testing."""
    from brain import messaging
    return messaging


@pytest.fixture
def brain_phases(temp_repo: Path):
    """Import brain.phases module for testing."""
    from brain import phases
    return phases


@pytest.fixture
def brain_missions(temp_repo: Path):
    """Import brain.missions module for testing."""
    from brain import missions
    return missions


@pytest.fixture
def brain_cli_path() -> Path:
    """Return path to brain_cli.py entry point."""
    return Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"


@pytest.fixture
def brain_script_path() -> Path:
    """Return path to brain.py legacy script."""
    return Path(__file__).parent.parent / "src" / "brain" / "brain.py"


@pytest.fixture
def hook_path() -> Path:
    """Return path to pre-commit-brain hook."""
    return Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"


# =============================================================================
# Identity fixtures
# =============================================================================

@pytest.fixture
def identity_file(temp_repo: Path) -> Path:
    """Create .brain directory and return path to self.json."""
    brain_dir = temp_repo / ".brain"
    brain_dir.mkdir(exist_ok=True)
    return brain_dir / "self.json"


@pytest.fixture
def sample_identity() -> dict:
    """Sample identity data (v3 format with color/emotion)."""
    return {
        "uuid": "12345678-1234-1234-1234-123456789abc",
        "short_name": "testuser",
        "color": "emerald",
        "emotion": "swift",
        "full_id": "testuser-emerald-swift",
        "emoji": "\U0001F916",
        "created_at": "2025-12-03T10:00:00+00:00",
        "version": 3,
        "has_keys": False,
        "public_key_fingerprint": None
    }


@pytest.fixture
def sample_identity_v1() -> dict:
    """Sample identity data (v1 format for backward compat tests)."""
    return {
        "uuid": "12345678-1234-1234-1234-123456789abc",
        "short_uuid": "12345678",
        "short_name": "testuser",
        "full_id": "testuser-abcd1234",
        "created_at": "2025-12-03T10:00:00+00:00",
        "version": 1
    }


@pytest.fixture
def initialized_identity(identity_file: Path, sample_identity: dict) -> dict:
    """Create an initialized identity and return it."""
    with open(identity_file, "w") as f:
        json.dump(sample_identity, f)
    os.chmod(identity_file, 0o600)
    return sample_identity


# =============================================================================
# Mission fixtures
# =============================================================================

@pytest.fixture
def missions_dir(temp_repo: Path) -> Path:
    """Create .brain/missions directories and return active dir."""
    active_dir = temp_repo / ".brain" / "missions" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    (temp_repo / ".brain" / "missions" / "completed").mkdir(exist_ok=True)
    (temp_repo / ".brain" / "missions" / "abandoned").mkdir(exist_ok=True)
    return active_dir


@pytest.fixture
def sample_mission() -> dict:
    """Sample mission data."""
    return {
        "id": "mission-test123",
        "title": "Test Mission",
        "description": "A test mission for unit tests",
        "status": "planning",
        "strategy": {
            "approach": "sequential",
            "priority": "normal",
            "rationale": "",
            "risks": []
        },
        "tasks": [],
        "dod": {
            "required": [],
            "optional": [],
            "automated": []
        },
        "before_code": {
            "items": [],
            "completed_at": None,
            "completed_by": None
        },
        "before_commit": {
            "manual": [],
            "automated": [],
            "enforced": True
        },
        "created_by": "@testuser",
        "created_at": "2025-12-03T10:00:00+00:00",
        "updated_at": "2025-12-03T10:00:00+00:00",
        "completed_at": None,
        "deadline": None
    }


@pytest.fixture
def sample_task() -> dict:
    """Sample task data."""
    return {
        "id": "task-abc123",
        "title": "Test Task",
        "task_type": "other",
        "description": None,
        "status": "pending",
        "phase_id": None,
        "depends_on": [],
        "claimed_by": None,
        "claimed_at": None,
        "assigned_to": None,
        "started_at": None,
        "completed_at": None,
        "pr": None
    }
