"""
Tests for mission.py - MissionOnHand management.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestMissionCreation:
    """Test mission creation."""
    
    def test_create_mission_basic(self, temp_repo, sample_identity):
        """Creating a mission should create a JSON file."""
        # Setup identity
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Test Mission"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "Mission created" in result.stdout
    
    def test_create_mission_with_options(self, temp_repo, sample_identity):
        """Creating mission with options should set them."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", 
             "High Priority Mission",
             "--priority", "high",
             "--approach", "parallel",
             "--description", "Test description"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "Mission created" in result.stdout
    
    def test_create_mission_generates_id(self, temp_repo, sample_identity):
        """Created mission should have a generated ID."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "ID Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert "mission-" in result.stdout


class TestMissionList:
    """Test mission listing."""
    
    def test_list_empty(self, temp_repo, sample_identity):
        """Listing with no missions should show empty message."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "list"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "No missions" in result.stdout or "Missions" in result.stdout
    
    def test_list_shows_missions(self, temp_repo, sample_identity):
        """Listing should show created missions."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create a mission first
        subprocess.run(
            [sys.executable, str(mission_path), "create", "List Test Mission"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "list"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "List Test Mission" in result.stdout


class TestMissionShow:
    """Test mission details display."""
    
    def test_show_nonexistent(self, temp_repo, sample_identity):
        """Showing nonexistent mission should fail."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "show", "nonexistent-id"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1
        assert "not found" in result.stdout.lower()
    
    def test_show_displays_details(self, temp_repo, sample_identity):
        """Showing mission should display all sections."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Show Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Extract mission ID
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        assert match
        mission_id = match.group(1)
        
        # Show it
        result = subprocess.run(
            [sys.executable, str(mission_path), "show", mission_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "MISSION:" in result.stdout
        assert "STRATEGY" in result.stdout
        assert "TASKS" in result.stdout
        assert "BEFORE CODE" in result.stdout
        assert "DEFINITION OF DONE" in result.stdout


class TestTasks:
    """Test task management."""
    
    def test_add_task(self, temp_repo, sample_identity):
        """Adding task should succeed."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Task Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Add task
        result = subprocess.run(
            [sys.executable, str(mission_path), "task", "add", 
             mission_id, "My First Task", "--type", "bugfix"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "Task added" in result.stdout
    
    def test_start_task(self, temp_repo, sample_identity):
        """Starting task should update status."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Start Task Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Add task
        result = subprocess.run(
            [sys.executable, str(mission_path), "task", "add", 
             mission_id, "Task To Start"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        match = re.search(r'(task-[a-f0-9]+)', result.stdout)
        task_id = match.group(1)
        
        # Start task
        result = subprocess.run(
            [sys.executable, str(mission_path), "task", "start", 
             mission_id, task_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "Task started" in result.stdout
    
    def test_complete_task(self, temp_repo, sample_identity):
        """Completing task should update status."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Complete Task Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Add task
        result = subprocess.run(
            [sys.executable, str(mission_path), "task", "add", 
             mission_id, "Task To Complete"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        match = re.search(r'(task-[a-f0-9]+)', result.stdout)
        task_id = match.group(1)
        
        # Complete task
        result = subprocess.run(
            [sys.executable, str(mission_path), "task", "complete", 
             mission_id, task_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "Task completed" in result.stdout


class TestBeforeCode:
    """Test beforeCode checklist."""
    
    def test_beforecode_show(self, temp_repo, sample_identity):
        """Should show beforeCode checklist."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "BeforeCode Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Show beforecode
        result = subprocess.run(
            [sys.executable, str(mission_path), "beforecode", "show", mission_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "BEFORE CODE CHECKLIST" in result.stdout
        assert "bc-1" in result.stdout
    
    def test_beforecode_check_item(self, temp_repo, sample_identity):
        """Should be able to check an item."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Check Item Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Check an item
        result = subprocess.run(
            [sys.executable, str(mission_path), "beforecode", "check", 
             mission_id, "bc-1"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "Checked" in result.stdout
    
    def test_beforecode_uncheck_item(self, temp_repo, sample_identity):
        """Should be able to uncheck an item."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Uncheck Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Check then uncheck
        subprocess.run(
            [sys.executable, str(mission_path), "beforecode", "check", 
             mission_id, "bc-1"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "beforecode", "check", 
             mission_id, "bc-1", "--uncheck"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "Unchecked" in result.stdout


class TestDoD:
    """Test Definition of Done."""
    
    def test_dod_show(self, temp_repo, sample_identity):
        """Should show DoD."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "DoD Show Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Show DoD
        result = subprocess.run(
            [sys.executable, str(mission_path), "dod", "show", mission_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "DEFINITION OF DONE" in result.stdout
        assert "REQUIRED" in result.stdout
        assert "dod-1" in result.stdout
    
    def test_dod_verify_criterion(self, temp_repo, sample_identity):
        """Should be able to verify a criterion."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "DoD Verify Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Verify criterion
        result = subprocess.run(
            [sys.executable, str(mission_path), "dod", "verify", 
             mission_id, "dod-1", "--evidence", "All tasks done"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "Verified" in result.stdout


class TestMissionStart:
    """Test mission start."""
    
    def test_start_requires_beforecode(self, temp_repo, sample_identity):
        """Starting should require beforeCode completion."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Start Require Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Try to start without completing beforeCode
        result = subprocess.run(
            [sys.executable, str(mission_path), "start", mission_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1
        assert "beforeCode" in result.stdout or "incomplete" in result.stdout
    
    def test_start_with_force(self, temp_repo, sample_identity):
        """Starting with --force should skip beforeCode check."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create mission
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Force Start Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Force start
        result = subprocess.run(
            [sys.executable, str(mission_path), "start", mission_id, "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "started" in result.stdout


class TestMissionComplete:
    """Test mission completion."""
    
    def test_complete_requires_dod(self, temp_repo, sample_identity):
        """Completing should require DoD verification."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create and force start
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Complete Require Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        subprocess.run(
            [sys.executable, str(mission_path), "start", mission_id, "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Try to complete without DoD
        result = subprocess.run(
            [sys.executable, str(mission_path), "complete", mission_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1
        assert "DoD" in result.stdout
    
    def test_complete_with_force(self, temp_repo, sample_identity):
        """Completing with --force should skip DoD check."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        # Create and force start
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Force Complete Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        subprocess.run(
            [sys.executable, str(mission_path), "start", mission_id, "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Force complete
        result = subprocess.run(
            [sys.executable, str(mission_path), "complete", mission_id, "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "completed" in result.stdout


class TestMissionStorage:
    """Test mission file storage."""
    
    def test_mission_saved_to_active(self, temp_repo, sample_identity):
        """New mission should be saved to active directory."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Storage Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Check file exists in active
        active_dir = temp_repo / ".brain" / "missions" / "active"
        assert (active_dir / f"{mission_id}.json").exists()
    
    def test_completed_moved_to_completed(self, temp_repo, sample_identity):
        """Completed mission should be moved to completed directory."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Move Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        # Force start and complete
        subprocess.run(
            [sys.executable, str(mission_path), "start", mission_id, "--force"],
            cwd=temp_repo, capture_output=True
        )
        subprocess.run(
            [sys.executable, str(mission_path), "complete", mission_id, "--force"],
            cwd=temp_repo, capture_output=True
        )
        
        # Check file in completed
        completed_dir = temp_repo / ".brain" / "missions" / "completed"
        assert (completed_dir / f"{mission_id}.json").exists()
        
        # Check not in active
        active_dir = temp_repo / ".brain" / "missions" / "active"
        assert not (active_dir / f"{mission_id}.json").exists()


class TestDefaultChecklists:
    """Test default checklist content."""
    
    def test_default_beforecode_items(self, temp_repo, sample_identity):
        """Should have default beforeCode items."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Default BC Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "beforecode", "show", mission_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should have brain sync item
        assert "brain sync" in result.stdout.lower() or "receipt" in result.stdout.lower()
    
    def test_default_dod_items(self, temp_repo, sample_identity):
        """Should have default DoD items."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        with open(brain_dir / "self.json", "w") as f:
            json.dump(sample_identity, f)
        
        mission_path = Path(__file__).parent.parent / "mission.py"
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "create", "Default DoD Test"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        import re
        match = re.search(r'(mission-[a-f0-9]+)', result.stdout)
        mission_id = match.group(1)
        
        result = subprocess.run(
            [sys.executable, str(mission_path), "dod", "show", mission_id],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should have tests pass item
        assert "test" in result.stdout.lower()

