#!/usr/bin/env python3
"""
mission.py - MissionOnHand management for AI agents

A Mission represents a high-level goal with:
- Strategy: How to approach the mission
- Tasks: Individual work items
- DoD: Definition of Done criteria
- beforeCode: Checklist before writing any code
- beforeCommit: Checklist before every commit

Usage:
    python scripts/mission.py create "Mission Title"
    python scripts/mission.py list
    python scripts/mission.py show <mission-id>
    python scripts/mission.py task add <mission-id> "Task title"
    python scripts/mission.py beforecode check <mission-id> <item-id>
    python scripts/mission.py dod verify <mission-id> <criterion-id>
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# =============================================================================
# Configuration
# =============================================================================

BRAIN_DIR = Path(".brain")
MISSIONS_DIR = BRAIN_DIR / "missions"
ACTIVE_DIR = MISSIONS_DIR / "active"
COMPLETED_DIR = MISSIONS_DIR / "completed"
ABANDONED_DIR = MISSIONS_DIR / "abandoned"


# =============================================================================
# Git Integration
# =============================================================================

def run_git(*args, capture=True, check=True) -> subprocess.CompletedProcess:
    """Run a git command."""
    cmd = ["git"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check
    )


def git_output(*args) -> str:
    """Run git command and return stdout."""
    result = run_git(*args)
    return result.stdout.strip()


def safe_commit(message: str, files: list = None) -> tuple:
    """
    Commit files with error handling.
    
    Returns (success, commit_hash, error_message).
    On failure, prints clear error to stderr and returns False.
    """
    try:
        if files:
            run_git("add", *[str(f) for f in files])
        run_git("commit", "-m", message)
        commit_hash = git_output("rev-parse", "--short", "HEAD")
        return True, commit_hash, ""
    except subprocess.CalledProcessError as e:
        error_output = e.stderr if e.stderr else e.stdout if e.stdout else "Unknown error"
        error_msg = f"""
❌ COMMIT FAILED
{'─' * 50}
Command: git commit -m "{message[:50]}..."
Exit code: {e.returncode}

Error: {error_output[:200]}

Tips:
  • Run 'git status' to check staged files
  • Run 'pnpm run lint' to check for linter errors
  • Check pre-commit hook output above
{'─' * 50}
"""
        print(error_msg, file=sys.stderr)
        return False, "", error_output


def safe_git_push(remote: str = "origin", branch: str = None) -> bool:
    """Push to remote, handling errors gracefully."""
    try:
        if branch:
            run_git("push", remote, branch)
        else:
            run_git("push")
        return True
    except subprocess.CalledProcessError:
        print("⚠️  Push failed (no remote configured?)", file=sys.stderr)
        return False


# =============================================================================
# Enums
# =============================================================================

class MissionStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    BLOCKED = "blocked"
    PAUSED = "paused"
    COMPLETE = "complete"
    ABANDONED = "abandoned"


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    SKIPPED = "skipped"


class TaskType(str, Enum):
    PHASE = "phase"
    BUGFIX = "bugfix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    REVIEW = "review"
    OTHER = "other"


class StrategyApproach(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class CheckType(str, Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    REVIEW = "review"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AutomatedCheck:
    """An automated check that runs a command."""
    id: str
    description: str
    command: str
    expected_exit_code: int = 0
    last_run: Optional[str] = None
    last_result: Optional[str] = None  # 'pass' | 'fail'


@dataclass
class ChecklistItem:
    """A manual checklist item."""
    id: str
    description: str
    required: bool = True
    checked: bool = False
    checked_by: Optional[str] = None
    checked_at: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class DoDCriterion:
    """A Definition of Done criterion."""
    id: str
    description: str
    check_type: str = "manual"  # manual | automated | review
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class BeforeCodeChecklist:
    """Checklist to complete before writing any code."""
    items: list = field(default_factory=list)
    completed_at: Optional[str] = None
    completed_by: Optional[str] = None
    
    @classmethod
    def default(cls) -> 'BeforeCodeChecklist':
        """Create default beforeCode checklist."""
        return cls(items=[
            ChecklistItem(
                id="bc-1",
                description="Run `brain sync` and `brain receipt`",
                required=True
            ),
            ChecklistItem(
                id="bc-2",
                description="Read relevant documentation and understand context",
                required=True
            ),
            ChecklistItem(
                id="bc-3",
                description="Check for dependencies and blockers",
                required=True
            ),
            ChecklistItem(
                id="bc-4",
                description="Understand WHY before fixing WHAT (root cause analysis)",
                required=True
            ),
            ChecklistItem(
                id="bc-5",
                description="Review existing tests for expected behavior",
                required=True
            ),
            ChecklistItem(
                id="bc-6",
                description="Verify no one else is working on related code",
                required=False
            ),
            ChecklistItem(
                id="bc-7",
                description="Plan approach and identify risks",
                required=False
            ),
        ])


@dataclass
class BeforeCommitChecklist:
    """Checklist to complete before every commit."""
    manual: list = field(default_factory=list)
    automated: list = field(default_factory=list)
    enforced: bool = True
    
    @classmethod
    def default(cls) -> 'BeforeCommitChecklist':
        """Create default beforeCommit checklist."""
        return cls(
            enforced=True,
            manual=[
                ChecklistItem(
                    id="commit-1",
                    description="Code is production-ready (no TODOs, no stubs, no placeholders)",
                    required=True
                ),
                ChecklistItem(
                    id="commit-2",
                    description="Commit message follows format: type(scope): description",
                    required=True
                ),
                ChecklistItem(
                    id="commit-3",
                    description="No secrets or sensitive data in commit",
                    required=True
                ),
                ChecklistItem(
                    id="commit-4",
                    description="Changes are minimal and focused (single responsibility)",
                    required=True
                ),
                ChecklistItem(
                    id="commit-5",
                    description="Self-reviewed the diff before committing",
                    required=True
                ),
            ],
            automated=[
                AutomatedCheck(
                    id="auto-1",
                    description="Brain identity and receipt valid",
                    command="python scripts/hooks/pre-commit-brain",
                    expected_exit_code=0
                ),
                AutomatedCheck(
                    id="auto-2",
                    description="TypeScript compiles",
                    command="pnpm run typecheck",
                    expected_exit_code=0
                ),
                AutomatedCheck(
                    id="auto-3",
                    description="Linting passes",
                    command="pnpm run lint",
                    expected_exit_code=0
                ),
            ]
        )


@dataclass
class DefinitionOfDone:
    """Definition of Done for a mission."""
    required: list = field(default_factory=list)
    optional: list = field(default_factory=list)
    automated: list = field(default_factory=list)
    
    @classmethod
    def default(cls) -> 'DefinitionOfDone':
        """Create default DoD."""
        return cls(
            required=[
                DoDCriterion(
                    id="dod-1",
                    description="All tasks completed",
                    check_type="manual"
                ),
                DoDCriterion(
                    id="dod-2",
                    description="All tests pass",
                    check_type="automated"
                ),
                DoDCriterion(
                    id="dod-3",
                    description="Code reviewed (self or peer)",
                    check_type="review"
                ),
                DoDCriterion(
                    id="dod-4",
                    description="Documentation updated if needed",
                    check_type="manual"
                ),
            ],
            automated=[
                AutomatedCheck(
                    id="dod-auto-1",
                    description="Full validation passes",
                    command="pnpm run validate",
                    expected_exit_code=0
                ),
            ]
        )


@dataclass
class Task:
    """A task within a mission."""
    id: str
    title: str
    task_type: str = "other"
    description: Optional[str] = None
    status: str = "pending"
    phase_id: Optional[int] = None
    depends_on: list = field(default_factory=list)
    blocked_by: list = field(default_factory=list)
    assigned_to: Optional[str] = None
    branch: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    pr: Optional[str] = None
    acceptance_criteria: list = field(default_factory=list)
    validation_command: Optional[str] = None


@dataclass  
class Strategy:
    """Mission execution strategy."""
    approach: str = "sequential"
    priority: str = "normal"
    task_order: list = field(default_factory=list)
    parallel_groups: list = field(default_factory=list)
    max_concurrent_tasks: int = 1
    requires_review: bool = True
    rationale: str = ""
    risks: list = field(default_factory=list)
    mitigations: list = field(default_factory=list)


@dataclass
class MissionOnHand:
    """A mission with tasks, strategy, and quality gates."""
    id: str
    title: str
    description: str = ""
    status: str = "planning"
    
    # Core components
    strategy: Strategy = field(default_factory=Strategy)
    tasks: list = field(default_factory=list)
    
    # Quality gates
    dod: DefinitionOfDone = field(default_factory=DefinitionOfDone.default)
    before_code: BeforeCodeChecklist = field(default_factory=BeforeCodeChecklist.default)
    before_commit: BeforeCommitChecklist = field(default_factory=BeforeCommitChecklist.default)
    
    # Metadata
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    
    # Constraints
    deadline: Optional[str] = None
    blocked_by: list = field(default_factory=list)


# =============================================================================
# Utilities
# =============================================================================

def now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def generate_id(prefix: str = "mission") -> str:
    """Generate a unique ID."""
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def ensure_dirs():
    """Create mission directories if they don't exist."""
    for d in [MISSIONS_DIR, ACTIVE_DIR, COMPLETED_DIR, ABANDONED_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def load_identity() -> Optional[dict]:
    """Load brain identity."""
    identity_file = BRAIN_DIR / "self.json"
    if not identity_file.exists():
        return None
    try:
        with open(identity_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_identity_name() -> str:
    """Get identity short name or 'unknown'."""
    identity = load_identity()
    if identity:
        return f"@{identity.get('short_name', 'unknown')}"
    return "@unknown"


# =============================================================================
# Serialization
# =============================================================================

def dataclass_to_dict(obj) -> dict:
    """Convert dataclass to dict, handling nested dataclasses."""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: dataclass_to_dict(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, Enum):
        return obj.value
    else:
        return obj


def dict_to_checklist_item(d: dict) -> ChecklistItem:
    """Convert dict to ChecklistItem."""
    return ChecklistItem(**d)


def dict_to_automated_check(d: dict) -> AutomatedCheck:
    """Convert dict to AutomatedCheck."""
    return AutomatedCheck(**d)


def dict_to_dod_criterion(d: dict) -> DoDCriterion:
    """Convert dict to DoDCriterion."""
    return DoDCriterion(**d)


def dict_to_task(d: dict) -> Task:
    """Convert dict to Task."""
    return Task(**d)


def dict_to_strategy(d: dict) -> Strategy:
    """Convert dict to Strategy."""
    return Strategy(**d)


def dict_to_before_code(d: dict) -> BeforeCodeChecklist:
    """Convert dict to BeforeCodeChecklist."""
    items = [dict_to_checklist_item(item) for item in d.get('items', [])]
    return BeforeCodeChecklist(
        items=items,
        completed_at=d.get('completed_at'),
        completed_by=d.get('completed_by')
    )


def dict_to_before_commit(d: dict) -> BeforeCommitChecklist:
    """Convert dict to BeforeCommitChecklist."""
    manual = [dict_to_checklist_item(item) for item in d.get('manual', [])]
    automated = [dict_to_automated_check(item) for item in d.get('automated', [])]
    return BeforeCommitChecklist(
        manual=manual,
        automated=automated,
        enforced=d.get('enforced', True)
    )


def dict_to_dod(d: dict) -> DefinitionOfDone:
    """Convert dict to DefinitionOfDone."""
    required = [dict_to_dod_criterion(item) for item in d.get('required', [])]
    optional = [dict_to_dod_criterion(item) for item in d.get('optional', [])]
    automated = [dict_to_automated_check(item) for item in d.get('automated', [])]
    return DefinitionOfDone(required=required, optional=optional, automated=automated)


def dict_to_mission(d: dict) -> MissionOnHand:
    """Convert dict to MissionOnHand."""
    return MissionOnHand(
        id=d['id'],
        title=d['title'],
        description=d.get('description', ''),
        status=d.get('status', 'planning'),
        strategy=dict_to_strategy(d.get('strategy', {})),
        tasks=[dict_to_task(t) for t in d.get('tasks', [])],
        dod=dict_to_dod(d.get('dod', {})),
        before_code=dict_to_before_code(d.get('before_code', {})),
        before_commit=dict_to_before_commit(d.get('before_commit', {})),
        created_by=d.get('created_by', ''),
        created_at=d.get('created_at', ''),
        updated_at=d.get('updated_at', ''),
        completed_at=d.get('completed_at'),
        deadline=d.get('deadline'),
        blocked_by=d.get('blocked_by', [])
    )


# =============================================================================
# Mission Storage
# =============================================================================

def save_mission(mission: MissionOnHand) -> Path:
    """Save mission to file."""
    ensure_dirs()
    
    # Determine directory based on status
    if mission.status == MissionStatus.COMPLETE.value:
        directory = COMPLETED_DIR
    elif mission.status == MissionStatus.ABANDONED.value:
        directory = ABANDONED_DIR
    else:
        directory = ACTIVE_DIR
    
    filepath = directory / f"{mission.id}.json"
    
    # Update timestamp
    mission.updated_at = now_iso()
    
    with open(filepath, "w") as f:
        json.dump(dataclass_to_dict(mission), f, indent=2)
        f.write("\n")  # Trailing newline for Biome
    
    return filepath


def save_and_commit(mission: MissionOnHand, commit_msg: str, push: bool = False) -> tuple:
    """
    Save mission and commit to Git.
    
    Returns (filepath, success, commit_hash).
    """
    filepath = save_mission(mission)
    
    success, commit_hash, _ = safe_commit(commit_msg, [str(filepath)])
    
    if success and push:
        safe_git_push()
    
    return filepath, success, commit_hash


def load_mission(mission_id: str) -> Optional[MissionOnHand]:
    """Load mission by ID from any directory."""
    for directory in [ACTIVE_DIR, COMPLETED_DIR, ABANDONED_DIR]:
        filepath = directory / f"{mission_id}.json"
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
            return dict_to_mission(data)
    return None


def list_missions(status_filter: Optional[str] = None) -> list:
    """List all missions, optionally filtered by status."""
    ensure_dirs()
    missions = []
    
    directories = {
        'active': ACTIVE_DIR,
        'complete': COMPLETED_DIR,
        'abandoned': ABANDONED_DIR
    }
    
    for status, directory in directories.items():
        if status_filter and status != status_filter:
            continue
        
        for filepath in directory.glob("*.json"):
            try:
                with open(filepath) as f:
                    data = json.load(f)
                missions.append({
                    'id': data['id'],
                    'title': data['title'],
                    'status': data.get('status', status),
                    'tasks': len(data.get('tasks', [])),
                    'created_by': data.get('created_by', ''),
                    'updated_at': data.get('updated_at', '')
                })
            except (json.JSONDecodeError, IOError):
                pass
    
    return sorted(missions, key=lambda m: m.get('updated_at', ''), reverse=True)


def get_active_mission() -> Optional[MissionOnHand]:
    """Get the currently active mission (status=active)."""
    for filepath in ACTIVE_DIR.glob("*.json"):
        try:
            with open(filepath) as f:
                data = json.load(f)
            if data.get('status') == 'active':
                return dict_to_mission(data)
        except (json.JSONDecodeError, IOError):
            pass
    return None


# =============================================================================
# Automated Check Runner
# =============================================================================

def run_check(check: AutomatedCheck) -> tuple[bool, str]:
    """Run an automated check and return (passed, output)."""
    try:
        result = subprocess.run(
            check.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        passed = result.returncode == check.expected_exit_code
        output = result.stdout + result.stderr
        return passed, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Check timed out"
    except Exception as e:
        return False, str(e)


# =============================================================================
# CLI Commands
# =============================================================================

def cmd_create(args):
    """Create a new mission."""
    title = " ".join(args.title)
    
    mission = MissionOnHand(
        id=generate_id("mission"),
        title=title,
        description=args.description or "",
        status=MissionStatus.PLANNING.value,
        created_by=get_identity_name(),
        created_at=now_iso(),
        updated_at=now_iso(),
        strategy=Strategy(
            approach=args.approach or "sequential",
            priority=args.priority or "normal",
            rationale=""
        ),
        dod=DefinitionOfDone.default(),
        before_code=BeforeCodeChecklist.default(),
        before_commit=BeforeCommitChecklist.default()
    )
    
    push = getattr(args, 'push', False)
    filepath, success, commit_hash = save_and_commit(
        mission,
        f"mission(create): {mission.id} - {title[:40]}",
        push=push
    )
    
    print(f"✅ Mission created: {mission.id}")
    print(f"   Title: {mission.title}")
    print(f"   Status: {mission.status}")
    if success:
        print(f"   📝 Commit: {commit_hash}")
        if push:
            print(f"   📤 Pushed")
    print(f"   📁 Saved to: {filepath}")


def cmd_list(args):
    """List all missions."""
    missions = list_missions(args.status)
    
    if not missions:
        print("📭 No missions found")
        return
    
    print(f"\n📋 Missions ({len(missions)}):")
    print("─" * 70)
    
    for m in missions:
        status_emoji = {
            'planning': '📝',
            'active': '🔥',
            'blocked': '🔴',
            'paused': '⏸️',
            'complete': '✅',
            'abandoned': '❌'
        }.get(m['status'], '❓')
        
        print(f"{status_emoji} [{m['id']}] {m['title']}")
        print(f"   Status: {m['status']} | Tasks: {m['tasks']} | By: {m['created_by']}")
    
    print("─" * 70)


def cmd_show(args):
    """Show mission details."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    print()
    print("═" * 70)
    print(f"🎯 MISSION: {mission.title}")
    print("═" * 70)
    print(f"ID:          {mission.id}")
    print(f"Status:      {mission.status}")
    print(f"Created by:  {mission.created_by}")
    print(f"Created at:  {mission.created_at[:19]}")
    print(f"Updated at:  {mission.updated_at[:19]}")
    
    if mission.description:
        print(f"\nDescription: {mission.description}")
    
    # Strategy
    print("\n📊 STRATEGY")
    print("─" * 40)
    print(f"Approach:    {mission.strategy.approach}")
    print(f"Priority:    {mission.strategy.priority}")
    if mission.strategy.rationale:
        print(f"Rationale:   {mission.strategy.rationale}")
    
    # Tasks
    print(f"\n📋 TASKS ({len(mission.tasks)})")
    print("─" * 40)
    if mission.tasks:
        for task in mission.tasks:
            status_emoji = {
                'pending': '⬜',
                'ready': '🟡',
                'in_progress': '🔵',
                'in_review': '🟣',
                'blocked': '🔴',
                'complete': '✅',
                'skipped': '⏭️'
            }.get(task.status, '❓')
            print(f"  {status_emoji} [{task.id}] {task.title}")
    else:
        print("  (no tasks yet)")
    
    # Before Code
    bc_checked = sum(1 for item in mission.before_code.items if item.checked)
    bc_required = sum(1 for item in mission.before_code.items if item.required)
    print(f"\n📝 BEFORE CODE ({bc_checked}/{len(mission.before_code.items)} checked)")
    print("─" * 40)
    for item in mission.before_code.items[:3]:  # Show first 3
        emoji = "✅" if item.checked else ("⬜" if item.required else "◽")
        print(f"  {emoji} {item.description[:50]}")
    if len(mission.before_code.items) > 3:
        print(f"  ... and {len(mission.before_code.items) - 3} more")
    
    # DoD
    dod_verified = sum(1 for c in mission.dod.required if c.verified)
    print(f"\n✅ DEFINITION OF DONE ({dod_verified}/{len(mission.dod.required)} verified)")
    print("─" * 40)
    for criterion in mission.dod.required[:3]:
        emoji = "✅" if criterion.verified else "⬜"
        print(f"  {emoji} {criterion.description[:50]}")
    if len(mission.dod.required) > 3:
        print(f"  ... and {len(mission.dod.required) - 3} more")
    
    print("═" * 70)


def cmd_start(args):
    """Start a mission (set to active)."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    # Check beforeCode completion
    required_unchecked = [
        item for item in mission.before_code.items 
        if item.required and not item.checked
    ]
    
    if required_unchecked and not args.force:
        print("❌ Cannot start mission - beforeCode checklist incomplete:")
        for item in required_unchecked:
            print(f"  ⬜ {item.description}")
        print("\nComplete the checklist first or use --force to skip")
        sys.exit(1)
    
    mission.status = MissionStatus.ACTIVE.value
    mission.updated_at = now_iso()
    
    _, success, commit_hash = save_and_commit(
        mission,
        f"mission(start): {mission.id}"
    )
    
    print(f"🔥 Mission started: {mission.title}")
    if success:
        print(f"   📝 Commit: {commit_hash}")


def cmd_task_add(args):
    """Add a task to a mission."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    task = Task(
        id=generate_id("task"),
        title=" ".join(args.title),
        task_type=args.type or "other",
        description=args.description,
        status=TaskStatus.PENDING.value
    )
    
    mission.tasks.append(task)
    
    _, success, commit_hash = save_and_commit(
        mission,
        f"mission(task): add {task.id} to {mission.id}"
    )
    
    print(f"✅ Task added: {task.id}")
    print(f"   Title: {task.title}")
    if success:
        print(f"   📝 Commit: {commit_hash}")


def cmd_task_start(args):
    """Start working on a task."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    task = next((t for t in mission.tasks if t.id == args.task_id), None)
    
    if not task:
        print(f"❌ Task not found: {args.task_id}")
        sys.exit(1)
    
    task.status = TaskStatus.IN_PROGRESS.value
    task.started_at = now_iso()
    task.assigned_to = get_identity_name()
    
    _, success, commit_hash = save_and_commit(
        mission,
        f"mission(task): start {task.id}"
    )
    
    print(f"🔵 Task started: {task.title}")
    if success:
        print(f"   📝 Commit: {commit_hash}")


def cmd_task_complete(args):
    """Mark a task as complete."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    task = next((t for t in mission.tasks if t.id == args.task_id), None)
    
    if not task:
        print(f"❌ Task not found: {args.task_id}")
        sys.exit(1)
    
    task.status = TaskStatus.COMPLETE.value
    task.completed_at = now_iso()
    
    _, success, commit_hash = save_and_commit(
        mission,
        f"mission(task): complete {task.id}"
    )
    
    print(f"✅ Task completed: {task.title}")
    if success:
        print(f"   📝 Commit: {commit_hash}")


def cmd_beforecode_show(args):
    """Show beforeCode checklist."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    print(f"\n📝 BEFORE CODE CHECKLIST - {mission.title}")
    print("─" * 60)
    
    for item in mission.before_code.items:
        required = "🔴" if item.required else "◽"
        checked = "✅" if item.checked else "⬜"
        print(f"  {checked} [{item.id}] {required} {item.description}")
        if item.checked and item.checked_by:
            print(f"      └─ Checked by {item.checked_by} at {item.checked_at[:19]}")
    
    checked_count = sum(1 for item in mission.before_code.items if item.checked)
    total = len(mission.before_code.items)
    required_unchecked = sum(1 for item in mission.before_code.items if item.required and not item.checked)
    
    print("─" * 60)
    print(f"Progress: {checked_count}/{total} checked")
    if required_unchecked > 0:
        print(f"⚠️  {required_unchecked} required items unchecked")


def cmd_beforecode_check(args):
    """Check/uncheck a beforeCode item."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    item = next((i for i in mission.before_code.items if i.id == args.item_id), None)
    
    if not item:
        print(f"❌ Item not found: {args.item_id}")
        sys.exit(1)
    
    if args.uncheck:
        item.checked = False
        item.checked_by = None
        item.checked_at = None
        print(f"⬜ Unchecked: {item.description}")
    else:
        item.checked = True
        item.checked_by = get_identity_name()
        item.checked_at = now_iso()
        print(f"✅ Checked: {item.description}")
    
    # Check if all required items are done
    all_required_done = all(
        item.checked for item in mission.before_code.items if item.required
    )
    if all_required_done and not mission.before_code.completed_at:
        mission.before_code.completed_at = now_iso()
        mission.before_code.completed_by = get_identity_name()
        print("🎉 All required beforeCode items completed!")
    
    _, success, commit_hash = save_and_commit(
        mission,
        f"mission(beforecode): check {args.item_id}"
    )
    if success:
        print(f"   📝 Commit: {commit_hash}")


def cmd_dod_show(args):
    """Show Definition of Done."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    print(f"\n✅ DEFINITION OF DONE - {mission.title}")
    print("═" * 60)
    
    print("\n🔴 REQUIRED:")
    for c in mission.dod.required:
        emoji = "✅" if c.verified else "⬜"
        print(f"  {emoji} [{c.id}] {c.description}")
        if c.verified and c.verified_by:
            print(f"      └─ Verified by {c.verified_by}")
    
    if mission.dod.optional:
        print("\n◽ OPTIONAL:")
        for c in mission.dod.optional:
            emoji = "✅" if c.verified else "◽"
            print(f"  {emoji} [{c.id}] {c.description}")
    
    if mission.dod.automated:
        print("\n🤖 AUTOMATED CHECKS:")
        for check in mission.dod.automated:
            result_emoji = {"pass": "✅", "fail": "❌"}.get(check.last_result, "⬜")
            print(f"  {result_emoji} [{check.id}] {check.description}")
            print(f"      └─ Command: {check.command}")
    
    print("═" * 60)


def cmd_dod_verify(args):
    """Verify a DoD criterion."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    # Check in both required and optional
    criterion = None
    for c in mission.dod.required + mission.dod.optional:
        if c.id == args.criterion_id:
            criterion = c
            break
    
    if not criterion:
        print(f"❌ Criterion not found: {args.criterion_id}")
        sys.exit(1)
    
    criterion.verified = True
    criterion.verified_by = get_identity_name()
    criterion.verified_at = now_iso()
    if args.evidence:
        criterion.evidence = args.evidence
    
    _, success, commit_hash = save_and_commit(
        mission,
        f"mission(dod): verify {args.criterion_id}"
    )
    
    print(f"✅ Verified: {criterion.description}")
    if success:
        print(f"   📝 Commit: {commit_hash}")


def cmd_dod_run(args):
    """Run automated DoD checks."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    print(f"\n🤖 Running DoD automated checks for: {mission.title}")
    print("─" * 60)
    
    all_passed = True
    
    for check in mission.dod.automated:
        print(f"\n▶️  {check.description}")
        print(f"   Command: {check.command}")
        
        passed, output = run_check(check)
        
        check.last_run = now_iso()
        check.last_result = "pass" if passed else "fail"
        
        if passed:
            print(f"   ✅ PASSED")
        else:
            print(f"   ❌ FAILED")
            if output:
                print(f"   Output: {output[:200]}")
            all_passed = False
    
    _, success, commit_hash = save_and_commit(
        mission,
        f"mission(dod): run automated checks"
    )
    
    print("\n" + "─" * 60)
    if success:
        print(f"📝 Commit: {commit_hash}")
    if all_passed:
        print("✅ All automated checks passed!")
    else:
        print("❌ Some checks failed")
        sys.exit(1)


def cmd_complete(args):
    """Mark mission as complete."""
    mission = load_mission(args.mission_id)
    
    if not mission:
        print(f"❌ Mission not found: {args.mission_id}")
        sys.exit(1)
    
    # Check DoD
    unverified = [c for c in mission.dod.required if not c.verified]
    
    if unverified and not args.force:
        print("❌ Cannot complete mission - DoD not satisfied:")
        for c in unverified:
            print(f"  ⬜ {c.description}")
        print("\nVerify all DoD criteria first or use --force")
        sys.exit(1)
    
    # Move to completed
    old_path = ACTIVE_DIR / f"{mission.id}.json"
    
    mission.status = MissionStatus.COMPLETE.value
    mission.completed_at = now_iso()
    
    new_path = save_mission(mission)
    
    # Remove from active if it was there
    files_to_commit = [str(new_path)]
    if old_path.exists() and old_path != new_path:
        old_path.unlink()
        # Stage the deletion
        try:
            run_git("add", str(old_path))
        except subprocess.CalledProcessError:
            pass  # File might already be untracked
    
    success, commit_hash, _ = safe_commit(
        f"mission(complete): {mission.id}",
        files_to_commit
    )
    
    print(f"🎉 Mission completed: {mission.title}")
    if success:
        print(f"   📝 Commit: {commit_hash}")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MissionOnHand - Mission management for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # create
    p_create = subparsers.add_parser("create", help="Create a new mission")
    p_create.add_argument("title", nargs="+", help="Mission title")
    p_create.add_argument("--description", "-d", help="Mission description")
    p_create.add_argument("--approach", choices=["sequential", "parallel", "hybrid"])
    p_create.add_argument("--priority", choices=["critical", "high", "normal", "low"])
    p_create.add_argument("--push", "-p", action="store_true", help="Push after commit")
    
    # list
    p_list = subparsers.add_parser("list", help="List missions")
    p_list.add_argument("--status", choices=["active", "complete", "abandoned"])
    
    # show
    p_show = subparsers.add_parser("show", help="Show mission details")
    p_show.add_argument("mission_id", help="Mission ID")
    
    # start
    p_start = subparsers.add_parser("start", help="Start a mission")
    p_start.add_argument("mission_id", help="Mission ID")
    p_start.add_argument("--force", "-f", action="store_true", help="Skip beforeCode check")
    
    # complete
    p_complete = subparsers.add_parser("complete", help="Complete a mission")
    p_complete.add_argument("mission_id", help="Mission ID")
    p_complete.add_argument("--force", "-f", action="store_true", help="Skip DoD check")
    
    # task
    p_task = subparsers.add_parser("task", help="Task management")
    task_sub = p_task.add_subparsers(dest="task_command")
    
    p_task_add = task_sub.add_parser("add", help="Add a task")
    p_task_add.add_argument("mission_id", help="Mission ID")
    p_task_add.add_argument("title", nargs="+", help="Task title")
    p_task_add.add_argument("--type", choices=["phase", "bugfix", "feature", "refactor", "docs", "test", "review", "other"])
    p_task_add.add_argument("--description", "-d", help="Task description")
    
    p_task_start = task_sub.add_parser("start", help="Start a task")
    p_task_start.add_argument("mission_id", help="Mission ID")
    p_task_start.add_argument("task_id", help="Task ID")
    
    p_task_complete = task_sub.add_parser("complete", help="Complete a task")
    p_task_complete.add_argument("mission_id", help="Mission ID")
    p_task_complete.add_argument("task_id", help="Task ID")
    
    # beforecode
    p_bc = subparsers.add_parser("beforecode", help="Before code checklist")
    bc_sub = p_bc.add_subparsers(dest="bc_command")
    
    p_bc_show = bc_sub.add_parser("show", help="Show checklist")
    p_bc_show.add_argument("mission_id", help="Mission ID")
    
    p_bc_check = bc_sub.add_parser("check", help="Check an item")
    p_bc_check.add_argument("mission_id", help="Mission ID")
    p_bc_check.add_argument("item_id", help="Item ID")
    p_bc_check.add_argument("--uncheck", "-u", action="store_true", help="Uncheck instead")
    
    # dod
    p_dod = subparsers.add_parser("dod", help="Definition of Done")
    dod_sub = p_dod.add_subparsers(dest="dod_command")
    
    p_dod_show = dod_sub.add_parser("show", help="Show DoD")
    p_dod_show.add_argument("mission_id", help="Mission ID")
    
    p_dod_verify = dod_sub.add_parser("verify", help="Verify a criterion")
    p_dod_verify.add_argument("mission_id", help="Mission ID")
    p_dod_verify.add_argument("criterion_id", help="Criterion ID")
    p_dod_verify.add_argument("--evidence", "-e", help="Link to evidence")
    
    p_dod_run = dod_sub.add_parser("run", help="Run automated checks")
    p_dod_run.add_argument("mission_id", help="Mission ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Ensure we're in project root
    if not Path("package.json").exists():
        print("❌ Must run from project root", file=sys.stderr)
        sys.exit(1)
    
    # Dispatch
    if args.command == "create":
        cmd_create(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "complete":
        cmd_complete(args)
    elif args.command == "task":
        if args.task_command == "add":
            cmd_task_add(args)
        elif args.task_command == "start":
            cmd_task_start(args)
        elif args.task_command == "complete":
            cmd_task_complete(args)
        else:
            p_task.print_help()
    elif args.command == "beforecode":
        if args.bc_command == "show":
            cmd_beforecode_show(args)
        elif args.bc_command == "check":
            cmd_beforecode_check(args)
        else:
            p_bc.print_help()
    elif args.command == "dod":
        if args.dod_command == "show":
            cmd_dod_show(args)
        elif args.dod_command == "verify":
            cmd_dod_verify(args)
        elif args.dod_command == "run":
            cmd_dod_run(args)
        else:
            p_dod.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

