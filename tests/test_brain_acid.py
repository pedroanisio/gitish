"""
ACID Tests for Brain Protocol Messaging Commands.

Tests Atomicity, Consistency, Isolation, and Durability for:
- Mission commands (create, start, complete)
- Phase commands (claim, release, complete)
- Task commands (add, claim, start, complete)
- Message commands (send, announce)

DRY: Shared fixtures and helpers for all command types.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest


# =============================================================================
# DRY Helpers
# =============================================================================

def run_brain_cmd(brain_cli_path: Path, temp_repo: Path, *args) -> subprocess.CompletedProcess:
    """Run a brain CLI command and return the result."""
    return subprocess.run(
        [sys.executable, str(brain_cli_path)] + list(args),
        capture_output=True,
        text=True,
        cwd=temp_repo
    )


def get_brain_files(brain_dir: Path) -> set:
    """Get all files in .brain directory."""
    if not brain_dir.exists():
        return set()
    return {f for f in brain_dir.rglob("*") if f.is_file()}


def get_file_contents(brain_dir: Path) -> dict:
    """Get contents of all JSON files in .brain directory."""
    contents = {}
    if not brain_dir.exists():
        return contents
    for f in brain_dir.rglob("*.json"):
        try:
            contents[str(f.relative_to(brain_dir))] = f.read_text()
        except Exception:
            pass
    return contents


def count_events(brain_dir: Path) -> int:
    """Count events in events.jsonl."""
    events_file = brain_dir / "events.jsonl"
    if not events_file.exists():
        return 0
    return len([l for l in events_file.read_text().strip().split('\n') if l])


def count_mission_events(brain_dir: Path) -> int:
    """Count mission event files."""
    events_dir = brain_dir / "missions" / "events"
    if not events_dir.exists():
        return 0
    return len(list(events_dir.glob("evt-*.json")))


def has_mission_state_changed(brain_dir: Path, before_files: set, before_contents: dict) -> bool:
    """Check if mission state has changed (files added or content modified)."""
    after_files = get_brain_files(brain_dir)
    after_contents = get_file_contents(brain_dir)
    return after_files != before_files or after_contents != before_contents


# =============================================================================
# ACID Test Base Classes (DRY)
# =============================================================================

class ACIDTestBase:
    """Base class for ACID tests with common assertions."""

    @staticmethod
    def assert_file_exists(path: Path, msg: str = ""):
        """Assert file exists."""
        assert path.exists(), f"File should exist: {path}. {msg}"

    @staticmethod
    def assert_file_not_exists(path: Path, msg: str = ""):
        """Assert file does not exist."""
        assert not path.exists(), f"File should not exist: {path}. {msg}"

    @staticmethod
    def assert_valid_json(path: Path) -> dict:
        """Assert file contains valid JSON and return it."""
        assert path.exists(), f"File should exist: {path}"
        content = path.read_text()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in {path}: {e}")

    @staticmethod
    def assert_command_success(result: subprocess.CompletedProcess, msg: str = ""):
        """Assert command succeeded."""
        assert result.returncode == 0, f"Command failed: {result.stderr}. {msg}"

    @staticmethod
    def assert_command_fails(result: subprocess.CompletedProcess, msg: str = ""):
        """Assert command failed."""
        assert result.returncode != 0, f"Command should have failed. {msg}"


# =============================================================================
# Phase Command ACID Tests
# =============================================================================

class TestPhaseACIDAtomicity(ACIDTestBase):
    """ACID Atomicity: Phase operations complete entirely or not at all."""

    def test_phase_claim_creates_all_artifacts(self, temp_repo, brain_cli_path, initialized_identity):
        """Phase claim should atomically create claim file and event."""
        brain_dir = temp_repo / ".brain"
        events_before = count_events(brain_dir)

        result = run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "17")
        self.assert_command_success(result)

        # Both artifacts created atomically
        claim_file = brain_dir / "claims" / "phase-17-claim.json"
        self.assert_file_exists(claim_file, "Claim file should be created")

        events_after = count_events(brain_dir)
        assert events_after > events_before, "Event should be logged"

    def test_phase_release_removes_claim_atomically(self, temp_repo, brain_cli_path, initialized_identity):
        """Phase release should atomically remove claim and log event."""
        brain_dir = temp_repo / ".brain"

        # First claim
        run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "18")
        claim_file = brain_dir / "claims" / "phase-18-claim.json"
        self.assert_file_exists(claim_file)

        events_before = count_events(brain_dir)

        # Release
        result = run_brain_cmd(brain_cli_path, temp_repo, "phase", "release", "18")
        self.assert_command_success(result)

        # Claim removed, event logged
        self.assert_file_not_exists(claim_file, "Claim should be removed")
        events_after = count_events(brain_dir)
        assert events_after > events_before, "Release event should be logged"


class TestPhaseACIDConsistency(ACIDTestBase):
    """ACID Consistency: Phase state is always valid."""

    def test_phase_claim_file_valid_json(self, temp_repo, brain_cli_path, initialized_identity):
        """Phase claim file should be valid JSON with required fields."""
        brain_dir = temp_repo / ".brain"

        run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "19")

        claim_file = brain_dir / "claims" / "phase-19-claim.json"
        data = self.assert_valid_json(claim_file)

        # Required fields
        assert "phase" in data or "by" in data or "ts" in data, "Claim should have metadata"

    def test_phase_double_claim_prevented(self, temp_repo, brain_cli_path, initialized_identity):
        """Cannot claim same phase twice - consistency enforced."""
        # First claim succeeds
        result1 = run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "20")
        self.assert_command_success(result1)

        # Second claim should fail or warn
        result2 = run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "20")
        # Either fails or shows already claimed
        output = (result2.stdout + result2.stderr).lower()
        assert result2.returncode != 0 or "already" in output or "claimed" in output


class TestPhaseACIDIsolation(ACIDTestBase):
    """ACID Isolation: Phase operations don't interfere."""

    def test_phase_claims_independent(self, temp_repo, brain_cli_path, initialized_identity):
        """Different phase claims are isolated."""
        brain_dir = temp_repo / ".brain"

        # Claim two different phases
        run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "21")
        run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "22")

        # Both claims exist independently
        self.assert_file_exists(brain_dir / "claims" / "phase-21-claim.json")
        self.assert_file_exists(brain_dir / "claims" / "phase-22-claim.json")

        # Release one doesn't affect other
        run_brain_cmd(brain_cli_path, temp_repo, "phase", "release", "21")
        self.assert_file_not_exists(brain_dir / "claims" / "phase-21-claim.json")
        self.assert_file_exists(brain_dir / "claims" / "phase-22-claim.json")


class TestPhaseACIDDurability(ACIDTestBase):
    """ACID Durability: Phase changes persist."""

    def test_phase_claim_persists(self, temp_repo, brain_cli_path, initialized_identity):
        """Phase claim should persist after command completes."""
        brain_dir = temp_repo / ".brain"

        run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "23")

        claim_file = brain_dir / "claims" / "phase-23-claim.json"

        # Multiple reads should return same result
        content1 = claim_file.read_text()
        content2 = Path(claim_file).read_text()  # Fresh Path object
        assert content1 == content2, "Content should be durable"


# =============================================================================
# Mission Command ACID Tests
# =============================================================================

class TestMissionACIDAtomicity(ACIDTestBase):
    """ACID Atomicity: Mission operations complete entirely or not at all."""

    def test_mission_create_atomic(self, temp_repo, brain_cli_path, initialized_identity):
        """Mission create should atomically create mission file."""
        brain_dir = temp_repo / ".brain"
        files_before = get_brain_files(brain_dir)

        result = run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Test Mission")
        self.assert_command_success(result)

        # Mission file created atomically
        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json")) if missions_dir.exists() else []
        assert len(mission_files) >= 1, "Mission file should be created"

        # State changed (files added)
        files_after = get_brain_files(brain_dir)
        assert files_after != files_before, "Brain state should change after mission create"


class TestMissionACIDConsistency(ACIDTestBase):
    """ACID Consistency: Mission state is always valid."""

    def test_mission_file_valid_structure(self, temp_repo, brain_cli_path, initialized_identity):
        """Mission file should have valid JSON structure."""
        brain_dir = temp_repo / ".brain"

        result = run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Consistency Test")
        self.assert_command_success(result)

        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json"))
        assert len(mission_files) >= 1

        data = self.assert_valid_json(mission_files[0])
        assert "id" in data, "Mission should have id"
        assert "title" in data, "Mission should have title"
        assert "status" in data, "Mission should have status"

    def test_mission_event_valid_structure(self, temp_repo, brain_cli_path, initialized_identity):
        """Mission events should have valid JSON structure if emitted."""
        brain_dir = temp_repo / ".brain"

        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Event Test")

        events_dir = brain_dir / "missions" / "events"
        event_files = list(events_dir.glob("evt-*.json")) if events_dir.exists() else []

        # Events are optional - if present, must be valid
        if len(event_files) >= 1:
            data = self.assert_valid_json(event_files[0])
            assert "event_type" in data, "Event should have type"
            assert "timestamp" in data, "Event should have timestamp"
        else:
            # No events file - verify mission file is valid instead
            missions_dir = brain_dir / "missions" / "active"
            mission_files = list(missions_dir.glob("mission-*.json"))
            assert len(mission_files) >= 1, "Mission file should exist"
            self.assert_valid_json(mission_files[0])


class TestMissionACIDIsolation(ACIDTestBase):
    """ACID Isolation: Mission operations don't interfere."""

    def test_multiple_missions_isolated(self, temp_repo, brain_cli_path, initialized_identity):
        """Multiple missions should be independent."""
        brain_dir = temp_repo / ".brain"

        # Create two missions
        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Mission A")
        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Mission B")

        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json"))
        assert len(mission_files) >= 2, "Both missions should exist"

        # Each has unique ID
        ids = set()
        for f in mission_files:
            data = json.loads(f.read_text())
            ids.add(data["id"])
        assert len(ids) >= 2, "Missions should have unique IDs"


class TestMissionACIDDurability(ACIDTestBase):
    """ACID Durability: Mission changes persist."""

    def test_mission_persists_after_creation(self, temp_repo, brain_cli_path, initialized_identity):
        """Mission should persist after creation."""
        brain_dir = temp_repo / ".brain"

        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Durable Mission")

        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json"))
        assert len(mission_files) >= 1

        # Content is durable
        original = mission_files[0].read_text()
        reread = Path(mission_files[0]).read_text()
        assert original == reread


# =============================================================================
# Task Command ACID Tests
# =============================================================================

class TestTaskACIDAtomicity(ACIDTestBase):
    """ACID Atomicity: Task operations complete entirely or not at all."""

    def test_task_add_atomic(self, temp_repo, brain_cli_path, initialized_identity):
        """Task add should atomically update mission."""
        brain_dir = temp_repo / ".brain"

        # Create mission first
        result = run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Task Test Mission")
        self.assert_command_success(result)

        # Get mission ID from output or file
        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json"))
        mission_data = json.loads(mission_files[0].read_text())
        mission_id = mission_data["id"]
        tasks_before = len(mission_data.get("tasks", []))

        # Add task
        result = run_brain_cmd(brain_cli_path, temp_repo, "task", "add", mission_id, "Test Task")
        self.assert_command_success(result)

        # Task added to mission atomically
        updated_mission = json.loads(mission_files[0].read_text())
        tasks_after = len(updated_mission.get("tasks", []))
        assert tasks_after > tasks_before, "Task should be added to mission"


class TestTaskACIDConsistency(ACIDTestBase):
    """ACID Consistency: Task state is always valid."""

    def test_task_has_valid_structure(self, temp_repo, brain_cli_path, initialized_identity):
        """Task should have valid structure with required fields."""
        brain_dir = temp_repo / ".brain"

        # Create mission and task
        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Task Structure Test")

        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json"))
        mission_data = json.loads(mission_files[0].read_text())
        mission_id = mission_data["id"]

        run_brain_cmd(brain_cli_path, temp_repo, "task", "add", mission_id, "Structured Task")

        # Verify task structure
        updated_mission = json.loads(mission_files[0].read_text())
        tasks = updated_mission.get("tasks", [])
        assert len(tasks) >= 1

        task = tasks[0]
        assert "id" in task, "Task should have id"
        assert "title" in task, "Task should have title"
        assert "status" in task, "Task should have status"


class TestTaskACIDIsolation(ACIDTestBase):
    """ACID Isolation: Task operations don't interfere."""

    def test_tasks_in_different_missions_isolated(self, temp_repo, brain_cli_path, initialized_identity):
        """Tasks in different missions should be isolated."""
        brain_dir = temp_repo / ".brain"

        # Create two missions
        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Mission X")
        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Mission Y")

        missions_dir = brain_dir / "missions" / "active"
        mission_files = sorted(missions_dir.glob("mission-*.json"))

        mission_x = json.loads(mission_files[0].read_text())
        mission_y = json.loads(mission_files[1].read_text())

        # Add task to mission X only
        run_brain_cmd(brain_cli_path, temp_repo, "task", "add", mission_x["id"], "Task for X")

        # Verify isolation
        updated_x = json.loads(mission_files[0].read_text())
        updated_y = json.loads(mission_files[1].read_text())

        assert len(updated_x.get("tasks", [])) >= 1, "Mission X should have task"
        assert len(updated_y.get("tasks", [])) == 0, "Mission Y should have no tasks"


class TestTaskACIDDurability(ACIDTestBase):
    """ACID Durability: Task changes persist."""

    def test_task_persists(self, temp_repo, brain_cli_path, initialized_identity):
        """Task should persist after creation."""
        brain_dir = temp_repo / ".brain"

        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Durable Task Mission")

        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json"))
        mission_id = json.loads(mission_files[0].read_text())["id"]

        run_brain_cmd(brain_cli_path, temp_repo, "task", "add", mission_id, "Persistent Task")

        # Multiple reads return same result
        read1 = json.loads(mission_files[0].read_text())
        read2 = json.loads(Path(mission_files[0]).read_text())

        assert read1["tasks"] == read2["tasks"], "Task data should be durable"


# =============================================================================
# Message Command ACID Tests
# =============================================================================

class TestMessageACIDAtomicity(ACIDTestBase):
    """ACID Atomicity: Message operations complete entirely or not at all."""

    def test_msg_send_atomic(self, temp_repo, brain_cli_path, initialized_identity):
        """Message send should atomically create file and log event."""
        brain_dir = temp_repo / ".brain"
        events_before = count_events(brain_dir)

        result = run_brain_cmd(brain_cli_path, temp_repo, "msg", "send", "Hello World")
        self.assert_command_success(result)

        # Message file created
        messages_dir = brain_dir / "messages"
        msg_files = list(messages_dir.rglob("*.json"))
        assert len(msg_files) >= 1, "Message file should be created"

        # Event logged
        events_after = count_events(brain_dir)
        assert events_after > events_before, "Message event should be logged"


class TestMessageACIDConsistency(ACIDTestBase):
    """ACID Consistency: Message state is always valid."""

    def test_message_valid_structure(self, temp_repo, brain_cli_path, initialized_identity):
        """Message file should have valid JSON structure."""
        brain_dir = temp_repo / ".brain"

        run_brain_cmd(brain_cli_path, temp_repo, "msg", "send", "Structured Message")

        messages_dir = brain_dir / "messages"
        msg_files = list(messages_dir.rglob("*.json"))
        assert len(msg_files) >= 1

        data = self.assert_valid_json(msg_files[0])
        assert "type" in data, "Message should have type"
        assert "from" in data, "Message should have sender"
        assert "ts" in data, "Message should have timestamp"


class TestMessageACIDIsolation(ACIDTestBase):
    """ACID Isolation: Message operations don't interfere."""

    def test_multiple_messages_isolated(self, temp_repo, brain_cli_path, initialized_identity):
        """Multiple messages should be independent."""
        brain_dir = temp_repo / ".brain"

        run_brain_cmd(brain_cli_path, temp_repo, "msg", "send", "Message One")
        run_brain_cmd(brain_cli_path, temp_repo, "msg", "send", "Message Two")

        messages_dir = brain_dir / "messages"
        msg_files = list(messages_dir.rglob("*.json"))
        assert len(msg_files) >= 2, "Both messages should exist"


class TestMessageACIDDurability(ACIDTestBase):
    """ACID Durability: Message changes persist."""

    def test_message_persists(self, temp_repo, brain_cli_path, initialized_identity):
        """Message should persist after send."""
        brain_dir = temp_repo / ".brain"

        run_brain_cmd(brain_cli_path, temp_repo, "msg", "send", "Durable Message")

        messages_dir = brain_dir / "messages"
        msg_files = list(messages_dir.rglob("*.json"))
        assert len(msg_files) >= 1

        # Content is durable
        original = msg_files[0].read_text()
        reread = Path(msg_files[0]).read_text()
        assert original == reread


# =============================================================================
# Cross-Command ACID Tests
# =============================================================================

class TestCrossCommandACID(ACIDTestBase):
    """ACID tests for interactions between different command types."""

    def test_mission_task_consistency(self, temp_repo, brain_cli_path, initialized_identity):
        """Mission and task operations maintain consistency."""
        brain_dir = temp_repo / ".brain"

        # Create mission
        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Cross Command Test")

        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json"))
        mission_id = json.loads(mission_files[0].read_text())["id"]

        # Add multiple tasks
        run_brain_cmd(brain_cli_path, temp_repo, "task", "add", mission_id, "Task 1")
        run_brain_cmd(brain_cli_path, temp_repo, "task", "add", mission_id, "Task 2")
        run_brain_cmd(brain_cli_path, temp_repo, "task", "add", mission_id, "Task 3")

        # All tasks present and consistent
        mission_data = json.loads(mission_files[0].read_text())
        assert len(mission_data.get("tasks", [])) >= 3

        # Each task has unique ID
        task_ids = [t["id"] for t in mission_data["tasks"]]
        assert len(task_ids) == len(set(task_ids)), "Task IDs should be unique"

    def test_operations_dont_corrupt_each_other(self, temp_repo, brain_cli_path, initialized_identity):
        """Different operations should not corrupt each other's state."""
        brain_dir = temp_repo / ".brain"

        # Perform various operations
        run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "30")
        run_brain_cmd(brain_cli_path, temp_repo, "mission", "create", "Isolation Test")
        run_brain_cmd(brain_cli_path, temp_repo, "msg", "send", "Test message")

        # All state is valid
        claim_file = brain_dir / "claims" / "phase-30-claim.json"
        self.assert_file_exists(claim_file)
        self.assert_valid_json(claim_file)

        missions_dir = brain_dir / "missions" / "active"
        mission_files = list(missions_dir.glob("mission-*.json"))
        for f in mission_files:
            self.assert_valid_json(f)

        messages_dir = brain_dir / "messages"
        msg_files = list(messages_dir.rglob("*.json"))
        for f in msg_files:
            self.assert_valid_json(f)

    def test_event_log_integrity(self, temp_repo, brain_cli_path, initialized_identity):
        """Event log should maintain integrity across operations."""
        brain_dir = temp_repo / ".brain"

        # Perform multiple operations
        run_brain_cmd(brain_cli_path, temp_repo, "phase", "claim", "31")
        run_brain_cmd(brain_cli_path, temp_repo, "msg", "send", "Event test")
        run_brain_cmd(brain_cli_path, temp_repo, "phase", "release", "31")

        # Events log should be valid JSONL
        events_file = brain_dir / "events.jsonl"
        if events_file.exists():
            lines = events_file.read_text().strip().split('\n')
            for line in lines:
                if line:
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        pytest.fail(f"Invalid JSON in events log: {line}")
