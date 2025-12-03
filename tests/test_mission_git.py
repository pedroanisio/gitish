"""
Tests for mission.py Git integration.

BUG: mission.py operations are local-only and don't commit to Git.
All mission operations should commit like brain.py does.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestMissionGitIntegration:
    """Test that mission operations commit to Git."""
    
    def test_create_mission_commits_to_git(self, temp_repo, mission_module):
        """Creating a mission should create a Git commit."""
        # Get initial commit count
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        initial_commits = int(result.stdout.strip())
        
        # Create mission
        class Args:
            title = ["Test Mission"]
            description = "Test description"
            approach = "sequential"
            priority = "normal"
        
        mission_module.cmd_mission_create(Args())
        
        # Should have one more commit
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        new_commits = int(result.stdout.strip())
        
        assert new_commits == initial_commits + 1, "Mission create should commit to Git"
    
    def test_create_mission_commit_message_format(self, temp_repo, mission_module):
        """Mission create commit should have proper message format."""
        class Args:
            title = ["Test Mission"]
            description = None
            approach = None
            priority = None
        
        mission_module.cmd_mission_create(Args())
        
        # Get last commit message
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            capture_output=True, text=True, cwd=temp_repo
        )
        commit_msg = result.stdout.strip()
        
        assert "mission" in commit_msg.lower(), f"Commit message should mention 'mission': {commit_msg}"
    
    def test_task_add_commits_to_git(self, temp_repo, mission_module):
        """Adding a task should create a Git commit."""
        # First create a mission
        class CreateArgs:
            title = ["Test Mission"]
            description = None
            approach = None
            priority = None
        
        mission_module.cmd_mission_create(CreateArgs())
        
        # Get mission ID
        missions = mission_module.list_missions()
        mid = missions[0]['id']
        
        # Get commit count
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        initial_commits = int(result.stdout.strip())
        
        # Add task
        class TaskArgs:
            pass
        TaskArgs.mission_id = mid
        TaskArgs.title = ["New Task"]
        TaskArgs.type = None
        TaskArgs.description = None
        
        mission_module.cmd_task_add(TaskArgs())
        
        # Should have one more commit
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        new_commits = int(result.stdout.strip())
        
        assert new_commits == initial_commits + 1, "Task add should commit to Git"
    
    def test_beforecode_check_commits_to_git(self, temp_repo, mission_module, initialized_identity):
        """Checking a beforeCode item should create a Git commit."""
        # Create mission
        class CreateArgs:
            title = ["Test Mission"]
            description = None
            approach = None
            priority = None
        
        mission_module.cmd_mission_create(CreateArgs())
        
        missions = mission_module.list_missions()
        mid = missions[0]['id']
        
        # Get commit count
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        initial_commits = int(result.stdout.strip())
        
        # Check beforeCode item
        class CheckArgs:
            pass
        CheckArgs.mission_id = mid
        CheckArgs.item_id = "bc-1"
        CheckArgs.uncheck = False
        
        mission_module.cmd_gate_check(CheckArgs())
        
        # Should have one more commit
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        new_commits = int(result.stdout.strip())
        
        assert new_commits == initial_commits + 1, "beforeCode check should commit to Git"
    
    def test_mission_start_commits_to_git(self, temp_repo, mission_module, initialized_identity):
        """Starting a mission should create a Git commit."""
        # Create mission and complete beforeCode
        class CreateArgs:
            title = ["Test Mission"]
            description = None
            approach = None
            priority = None
        
        mission_module.cmd_mission_create(CreateArgs())
        
        missions = mission_module.list_missions()
        mid = missions[0]['id']
        
        # Check all required beforeCode items
        mission = mission_module.load_mission(mid)
        for item in mission.before_code.items:
            if item.required:
                class CheckArgs:
                    pass
                CheckArgs.mission_id = mid
                CheckArgs.item_id = item.id
                CheckArgs.uncheck = False
                mission_module.cmd_gate_check(CheckArgs())
        
        # Get commit count
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        initial_commits = int(result.stdout.strip())
        
        # Start mission
        class StartArgs:
            pass
        StartArgs.mission_id = mid
        StartArgs.force = False
        
        mission_module.cmd_mission_start(StartArgs())
        
        # Should have one more commit
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        new_commits = int(result.stdout.strip())
        
        assert new_commits == initial_commits + 1, "Mission start should commit to Git"
    
    def test_dod_verify_commits_to_git(self, temp_repo, mission_module, initialized_identity):
        """Verifying a DoD criterion should create a Git commit."""
        # Create mission
        class CreateArgs:
            title = ["Test Mission"]
            description = None
            approach = None
            priority = None
        
        mission_module.cmd_mission_create(CreateArgs())
        
        missions = mission_module.list_missions()
        mid = missions[0]['id']
        
        # Get commit count
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        initial_commits = int(result.stdout.strip())
        
        # Verify DoD criterion
        class VerifyArgs:
            pass
        VerifyArgs.mission_id = mid
        VerifyArgs.criterion_id = "dod-1"
        VerifyArgs.evidence = "All tasks done"
        
        mission_module.cmd_gate_verify(VerifyArgs())
        
        # Should have one more commit
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        new_commits = int(result.stdout.strip())
        
        assert new_commits == initial_commits + 1, "DoD verify should commit to Git"
    
    def test_mission_complete_commits_to_git(self, temp_repo, mission_module):
        """Completing a mission should create a Git commit."""
        # Create mission
        class CreateArgs:
            title = ["Test Mission"]
            description = None
            approach = None
            priority = None
        
        mission_module.cmd_mission_create(CreateArgs())
        
        missions = mission_module.list_missions()
        mid = missions[0]['id']
        
        # Get commit count
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        initial_commits = int(result.stdout.strip())
        
        # Complete mission (force to skip DoD)
        class CompleteArgs:
            pass
        CompleteArgs.mission_id = mid
        CompleteArgs.force = True
        
        mission_module.cmd_mission_complete(CompleteArgs())
        
        # Should have one more commit
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=temp_repo
        )
        new_commits = int(result.stdout.strip())
        
        assert new_commits == initial_commits + 1, "Mission complete should commit to Git"


class TestMissionPushFlag:
    """Test --push flag for mission operations."""
    
    def test_create_with_push_flag(self, temp_repo, mission_module):
        """Mission create should support --push flag."""
        # This test verifies the flag exists and is handled
        class Args:
            title = ["Test Mission"]
            description = None
            approach = None
            priority = None
            push = True  # New flag
        
        # Should not crash - push will fail without remote but shouldn't error
        mission_module.cmd_mission_create(Args())
        
        missions = mission_module.list_missions()
        assert len(missions) == 1


class TestMissionFilesTracked:
    """Test that mission files are tracked in Git."""
    
    def test_mission_file_is_staged(self, temp_repo, mission_module):
        """Mission files should be staged after creation."""
        class Args:
            title = ["Test Mission"]
            description = None
            approach = None
            priority = None
        
        mission_module.cmd_mission_create(Args())
        
        # Check if mission file is tracked
        result = subprocess.run(
            ["git", "ls-files", ".brain/missions/"],
            capture_output=True, text=True, cwd=temp_repo
        )
        
        assert ".brain/missions/" in result.stdout or "mission-" in result.stdout, \
            "Mission files should be tracked in Git"

