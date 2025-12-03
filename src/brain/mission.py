"""
brain/missions.py - Mission Management Module

Multi-Agent Hierarchy:
    Mission (high-level goal, spans multiple agents)
        └── Phase (coordination unit, claimed by one agent via phase.py)
             └── Task (individual work item within a phase)

All stored via git in .brain/missions/ - fully multi-agent aware.

Commands:
- mission create/list/show/start/complete: Mission CRUD
- task add/start/complete: Task management (can link to phases via phase_id)
- gate beforecode/check/dod/verify/run: Quality gates
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import os
from typing import Optional

from .core import (
    BRAIN_DIR, ACTIVE_MISSIONS_DIR, COMPLETED_MISSIONS_DIR, ABANDONED_MISSIONS_DIR,
    MISSION_EVENTS_DIR, EVENTS_BRANCH,
    now_iso, generate_id,
    ensure_mission_dirs, ensure_brain_dirs, get_identity_name, get_current_branch, git_output,
    safe_commit, safe_push, save_json, load_json,
    run_git,
)


# =============================================================================
# Cross-Branch Mission Visibility (via branch aggregation)
# =============================================================================
#
# Architecture: Each agent stores missions on their own branch. When listing,
# we aggregate from all remote branches. This avoids push permission issues
# with shared branches.
#
# Pattern: UUID-based files avoid merge conflicts, timestamps enable local ordering.


# =============================================================================
# Event-Sourcing for Conflict-Free Multi-Agent Updates
# =============================================================================
#
# Architecture: Each state change is stored as an individual UUID-named event file.
# Events are immutable - once written, never modified. Mission state is computed
# by replaying all events in timestamp order.
#
# This eliminates merge conflicts because:
# - Each event has a unique filename (UUID)
# - Events are append-only, never edited
# - State is computed locally by replaying events
#
# Event flow:
# 1. Agent performs action (claim task, complete task, etc.)
# 2. Action emits an event file: .brain/missions/events/evt-<uuid>.json
# 3. Event is committed and pushed to agent's branch
# 4. On read, all events are aggregated from all branches
# 5. Events are sorted by timestamp and replayed to compute current state


class MissionEventType(str, Enum):
    """Types of mission events for event-sourcing."""
    MISSION_CREATED = "mission_created"
    MISSION_STARTED = "mission_started"
    MISSION_COMPLETED = "mission_completed"
    MISSION_ABANDONED = "mission_abandoned"
    TASK_ADDED = "task_added"
    TASK_CLAIMED = "task_claimed"
    TASK_RELEASED = "task_released"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_BLOCKED = "task_blocked"
    CHECKLIST_CHECKED = "checklist_checked"
    DOD_VERIFIED = "dod_verified"


@dataclass
class MissionEvent:
    """An immutable event representing a state change."""
    id: str  # Unique event ID (evt-<uuid>)
    event_type: str  # MissionEventType value
    mission_id: str  # Target mission
    timestamp: str  # ISO timestamp for ordering
    actor: str  # Who performed the action (full_id)
    data: dict = field(default_factory=dict)  # Event-specific payload


def emit_mission_event(
    event_type: MissionEventType,
    mission_id: str,
    actor: str,
    data: dict = None,
    push: bool = False
) -> Path:
    """
    Emit an immutable event for a mission state change.

    Events are stored as individual UUID-named files to avoid conflicts.
    Each agent writes to their own branch, events aggregate on read.
    """
    MISSION_EVENTS_DIR.mkdir(parents=True, exist_ok=True)

    event = MissionEvent(
        id=generate_id("evt"),
        event_type=event_type.value,
        mission_id=mission_id,
        timestamp=now_iso(),
        actor=actor,
        data=data or {}
    )

    filepath = MISSION_EVENTS_DIR / f"{event.id}.json"
    save_json(filepath, asdict(event))

    # Commit the event
    success, commit_hash, _ = safe_commit(
        f"event({event_type.value}): {mission_id} by {actor}",
        [str(filepath)]
    )

    if push and success:
        safe_push(get_current_branch())

    return filepath


def _read_events_from_branch(branch: str, mission_id: Optional[str] = None) -> list[dict]:
    """Read all mission events from a remote branch."""
    events = []

    try:
        result = run_git("ls-tree", "--name-only", branch, ".brain/missions/events/", check=False)
        if result.returncode != 0:
            return []

        for line in result.stdout.strip().split('\n'):
            if not line or not line.endswith('.json'):
                continue

            try:
                content_result = run_git("show", f"{branch}:{line}", check=False)
                if content_result.returncode == 0 and content_result.stdout.strip():
                    event_data = json.loads(content_result.stdout)
                    # Filter by mission_id if specified
                    if mission_id is None or event_data.get('mission_id') == mission_id:
                        event_data['_source_branch'] = branch
                        events.append(event_data)
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                continue
    except subprocess.CalledProcessError:
        pass

    return events


def read_mission_events(mission_id: Optional[str] = None) -> list[dict]:
    """
    Read all mission events from local and all remote branches.

    Returns events sorted by timestamp for replay ordering.
    Deduplicates by event ID (same event may exist on multiple branches).
    """
    events_by_id = {}

    # 1. Read local events
    if MISSION_EVENTS_DIR.exists():
        for filepath in MISSION_EVENTS_DIR.glob("*.json"):
            data = load_json(filepath)
            if data:
                if mission_id is None or data.get('mission_id') == mission_id:
                    events_by_id[data['id']] = data

    # 2. Read from all remote branches
    for branch in _get_remote_branches():
        for event_data in _read_events_from_branch(branch, mission_id):
            event_id = event_data['id']
            # Deduplicate - same event may be on multiple branches
            if event_id not in events_by_id:
                events_by_id[event_id] = event_data

    # Sort by timestamp for replay ordering
    events = list(events_by_id.values())
    return sorted(events, key=lambda e: e.get('timestamp', ''))


def apply_events_to_mission(mission: 'MissionOnHand', events: list[dict]) -> 'MissionOnHand':
    """
    Apply a list of events to a mission to compute current state.

    Events must be sorted by timestamp before calling this function.
    """
    for event in events:
        if event.get('mission_id') != mission.id:
            continue

        event_type = event.get('event_type')
        data = event.get('data', {})
        actor = event.get('actor', '')
        timestamp = event.get('timestamp', '')

        if event_type == MissionEventType.MISSION_STARTED.value:
            mission.status = MissionStatus.ACTIVE.value

        elif event_type == MissionEventType.MISSION_COMPLETED.value:
            mission.status = MissionStatus.COMPLETE.value
            mission.completed_at = timestamp

        elif event_type == MissionEventType.MISSION_ABANDONED.value:
            mission.status = MissionStatus.ABANDONED.value

        elif event_type == MissionEventType.TASK_CLAIMED.value:
            task_id = data.get('task_id')
            task = next((t for t in mission.tasks if t.id == task_id), None)
            if task:
                task.claimed_by = actor
                task.claimed_at = timestamp
                task.status = TaskStatus.READY.value

        elif event_type == MissionEventType.TASK_RELEASED.value:
            task_id = data.get('task_id')
            task = next((t for t in mission.tasks if t.id == task_id), None)
            if task:
                task.claimed_by = None
                task.claimed_at = None
                task.status = TaskStatus.PENDING.value

        elif event_type == MissionEventType.TASK_STARTED.value:
            task_id = data.get('task_id')
            task = next((t for t in mission.tasks if t.id == task_id), None)
            if task:
                task.status = TaskStatus.IN_PROGRESS.value
                task.started_at = timestamp
                task.assigned_to = actor

        elif event_type == MissionEventType.TASK_COMPLETED.value:
            task_id = data.get('task_id')
            task = next((t for t in mission.tasks if t.id == task_id), None)
            if task:
                task.status = TaskStatus.COMPLETE.value
                task.completed_at = timestamp

        elif event_type == MissionEventType.CHECKLIST_CHECKED.value:
            item_id = data.get('item_id')
            checked = data.get('checked', True)
            item = next((i for i in mission.before_code.items if i.id == item_id), None)
            if item:
                item.checked = checked
                if checked:
                    item.checked_by = actor
                    item.checked_at = timestamp
                else:
                    item.checked_by = None
                    item.checked_at = None

        elif event_type == MissionEventType.DOD_VERIFIED.value:
            criterion_id = data.get('criterion_id')
            evidence = data.get('evidence')
            criterion = next(
                (c for c in mission.dod.required + mission.dod.optional if c.id == criterion_id),
                None
            )
            if criterion:
                criterion.verified = True
                criterion.verified_by = actor
                criterion.verified_at = timestamp
                if evidence:
                    criterion.evidence = evidence

        # Update mission's updated_at to latest event
        if timestamp > (mission.updated_at or ''):
            mission.updated_at = timestamp

    return mission


def _get_remote_branches() -> list[str]:
    """Get all remote branches for mission aggregation."""
    run_git("fetch", "--all", check=False)
    result = run_git("branch", "-r", check=False)
    if result.returncode != 0:
        return []

    branches = []
    for line in result.stdout.strip().split('\n'):
        branch = line.strip()
        if branch and not branch.endswith('/HEAD'):
            branches.append(branch)
    return branches


def _read_missions_from_branch(branch: str) -> list[dict]:
    """Read all missions from a remote branch without checkout."""
    missions = []

    for subdir in ['active', 'completed', 'abandoned']:
        try:
            # List files in directory
            result = run_git("ls-tree", "--name-only", branch, f".brain/missions/{subdir}/", check=False)
            if result.returncode != 0:
                continue

            for line in result.stdout.strip().split('\n'):
                if not line or not line.endswith('.json'):
                    continue

                # Read file content
                try:
                    content_result = run_git("show", f"{branch}:{line}", check=False)
                    if content_result.returncode == 0 and content_result.stdout.strip():
                        data = json.loads(content_result.stdout)
                        data['_source_branch'] = branch
                        missions.append(data)
                except (subprocess.CalledProcessError, json.JSONDecodeError):
                    continue
        except subprocess.CalledProcessError:
            continue

    return missions


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


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ChecklistItem:
    """A manual checklist item."""
    id: str
    description: str
    required: bool = True
    checked: bool = False
    checked_by: Optional[str] = None
    checked_at: Optional[str] = None


@dataclass
class AutomatedCheck:
    """An automated check that runs a command."""
    id: str
    description: str
    command: str
    expected_exit_code: int = 0
    last_run: Optional[str] = None
    last_result: Optional[str] = None


@dataclass
class DoDCriterion:
    """A Definition of Done criterion."""
    id: str
    description: str
    check_type: str = "manual"
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
        return cls(items=[
            ChecklistItem(id="bc-1", description="Run `brain sync` and `brain receipt`", required=True),
            ChecklistItem(id="bc-2", description="Read relevant documentation and understand context", required=True),
            ChecklistItem(id="bc-3", description="Check for dependencies and blockers", required=True),
            ChecklistItem(id="bc-4", description="Understand WHY before fixing WHAT", required=True),
            ChecklistItem(id="bc-5", description="Review existing tests for expected behavior", required=True),
            ChecklistItem(id="bc-6", description="Verify no one else is working on related code", required=False),
            ChecklistItem(id="bc-7", description="Plan approach and identify risks", required=False),
        ])


@dataclass
class BeforeCommitChecklist:
    """Checklist to complete before every commit."""
    manual: list = field(default_factory=list)
    automated: list = field(default_factory=list)
    enforced: bool = True

    @classmethod
    def default(cls) -> 'BeforeCommitChecklist':
        return cls(
            enforced=True,
            manual=[
                ChecklistItem(id="commit-1", description="Code is production-ready (no TODOs, no stubs)", required=True),
                ChecklistItem(id="commit-2", description="Commit message follows format: type(scope): description", required=True),
                ChecklistItem(id="commit-3", description="No secrets or sensitive data in commit", required=True),
                ChecklistItem(id="commit-4", description="Changes are minimal and focused", required=True),
                ChecklistItem(id="commit-5", description="Self-reviewed the diff before committing", required=True),
            ],
            automated=[
                AutomatedCheck(id="auto-1", description="TypeScript compiles", command="pnpm run typecheck"),
                AutomatedCheck(id="auto-2", description="Linting passes", command="pnpm run lint"),
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
        return cls(
            required=[
                DoDCriterion(id="dod-1", description="All tasks completed", check_type="manual"),
                DoDCriterion(id="dod-2", description="All tests pass", check_type="automated"),
                DoDCriterion(id="dod-3", description="Code reviewed (self or peer)", check_type="review"),
                DoDCriterion(id="dod-4", description="Documentation updated if needed", check_type="manual"),
            ],
            automated=[
                AutomatedCheck(id="dod-auto-1", description="Full validation passes", command="pnpm run validate"),
            ]
        )


@dataclass
class Task:
    """
    A task within a mission.

    Multi-Agent Claiming:
    - Tasks can be claimed independently of phases
    - A task can be claimed even if the parent phase is claimed by another agent
    - Use `claimed_by`/`claimed_at` for ownership tracking
    """
    id: str
    title: str
    task_type: str = "other"
    description: Optional[str] = None
    status: str = "pending"
    phase_id: Optional[int] = None  # Links to a Phase (optional)
    depends_on: list = field(default_factory=list)
    # Claiming (independent from phase claims)
    claimed_by: Optional[str] = None  # full_id of claimer
    claimed_at: Optional[str] = None
    # Execution
    assigned_to: Optional[str] = None  # Who is working on it
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    pr: Optional[str] = None


@dataclass
class Strategy:
    """Mission execution strategy."""
    approach: str = "sequential"
    priority: str = "normal"
    rationale: str = ""
    risks: list = field(default_factory=list)


@dataclass
class MissionOnHand:
    """A mission with tasks, strategy, and quality gates."""
    id: str
    title: str
    description: str = ""
    status: str = "planning"
    strategy: Strategy = field(default_factory=Strategy)
    tasks: list = field(default_factory=list)
    dod: DefinitionOfDone = field(default_factory=DefinitionOfDone.default)
    before_code: BeforeCodeChecklist = field(default_factory=BeforeCodeChecklist.default)
    before_commit: BeforeCommitChecklist = field(default_factory=BeforeCommitChecklist.default)
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    deadline: Optional[str] = None


# =============================================================================
# Serialization
# =============================================================================

def dataclass_to_dict(obj) -> dict:
    """Convert dataclass to dict recursively."""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: dataclass_to_dict(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, Enum):
        return obj.value
    return obj


def dict_to_checklist_item(d: dict) -> ChecklistItem:
    return ChecklistItem(**{k: v for k, v in d.items() if k in ChecklistItem.__dataclass_fields__})


def dict_to_automated_check(d: dict) -> AutomatedCheck:
    return AutomatedCheck(**{k: v for k, v in d.items() if k in AutomatedCheck.__dataclass_fields__})


def dict_to_dod_criterion(d: dict) -> DoDCriterion:
    return DoDCriterion(**{k: v for k, v in d.items() if k in DoDCriterion.__dataclass_fields__})


def dict_to_task(d: dict) -> Task:
    return Task(**{k: v for k, v in d.items() if k in Task.__dataclass_fields__})


def dict_to_strategy(d: dict) -> Strategy:
    return Strategy(**{k: v for k, v in d.items() if k in Strategy.__dataclass_fields__})


def dict_to_before_code(d: dict) -> BeforeCodeChecklist:
    items = [dict_to_checklist_item(item) for item in d.get('items', [])]
    return BeforeCodeChecklist(
        items=items,
        completed_at=d.get('completed_at'),
        completed_by=d.get('completed_by')
    )


def dict_to_before_commit(d: dict) -> BeforeCommitChecklist:
    manual = [dict_to_checklist_item(item) for item in d.get('manual', [])]
    automated = [dict_to_automated_check(item) for item in d.get('automated', [])]
    return BeforeCommitChecklist(manual=manual, automated=automated, enforced=d.get('enforced', True))


def dict_to_dod(d: dict) -> DefinitionOfDone:
    required = [dict_to_dod_criterion(item) for item in d.get('required', [])]
    optional = [dict_to_dod_criterion(item) for item in d.get('optional', [])]
    automated = [dict_to_automated_check(item) for item in d.get('automated', [])]
    return DefinitionOfDone(required=required, optional=optional, automated=automated)


def dict_to_mission(d: dict) -> MissionOnHand:
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
        deadline=d.get('deadline')
    )


# =============================================================================
# Storage
# =============================================================================

def save_mission(mission: MissionOnHand) -> Path:
    """Save mission to file."""
    ensure_mission_dirs()

    if mission.status == MissionStatus.COMPLETE.value:
        directory = COMPLETED_MISSIONS_DIR
    elif mission.status == MissionStatus.ABANDONED.value:
        directory = ABANDONED_MISSIONS_DIR
    else:
        directory = ACTIVE_MISSIONS_DIR

    filepath = directory / f"{mission.id}.json"
    mission.updated_at = now_iso()
    save_json(filepath, dataclass_to_dict(mission))
    return filepath


def save_and_commit(mission: MissionOnHand, commit_msg: str, push: bool = False) -> tuple:
    """
    Save mission locally on the current branch and commit.

    Architecture: Each agent stores missions on their own branch. Cross-branch
    visibility is achieved by aggregating from all remote branches on read.
    This avoids permission issues with shared branches.
    """
    # Save mission locally
    filepath = save_mission(mission)

    # Commit locally
    success, commit_hash, _ = safe_commit(commit_msg, [str(filepath)])

    # Push to current branch if requested
    if push and success:
        safe_push(get_current_branch())

    return filepath, success, commit_hash


def load_mission(mission_id: str, apply_events: bool = True) -> Optional[MissionOnHand]:
    """
    Load mission by ID from local directories first, then all remote branches.

    Architecture: Checks local first (fast), then aggregates from remotes
    if not found locally. Then applies all events to compute current state.

    Args:
        mission_id: The mission ID to load
        apply_events: If True, apply all events to compute current state (default: True)
    """
    mission = None

    # Check local directories first (fast path)
    for directory in [ACTIVE_MISSIONS_DIR, COMPLETED_MISSIONS_DIR, ABANDONED_MISSIONS_DIR]:
        filepath = directory / f"{mission_id}.json"
        data = load_json(filepath)
        if data:
            mission = dict_to_mission(data)
            break

    # Search across all remote branches if not found locally
    if not mission:
        for branch in _get_remote_branches():
            for subdir in ['active', 'completed', 'abandoned']:
                try:
                    result = run_git("show", f"{branch}:.brain/missions/{subdir}/{mission_id}.json", check=False)
                    if result.returncode == 0 and result.stdout.strip():
                        data = json.loads(result.stdout)
                        mission = dict_to_mission(data)
                        break
                except (subprocess.CalledProcessError, json.JSONDecodeError):
                    continue
            if mission:
                break

    if not mission:
        return None

    # Apply events to compute current state
    if apply_events:
        events = read_mission_events(mission_id)
        if events:
            mission = apply_events_to_mission(mission, events)

    return mission


def list_missions(status_filter: Optional[str] = None) -> list:
    """
    List all missions from local directories AND all remote branches.

    Architecture: Aggregates missions from all sources, deduplicates by ID,
    keeping the most recently updated version.
    """
    missions_by_id = {}

    # 1. Read from local directories first
    ensure_mission_dirs()
    directories = {
        'active': ACTIVE_MISSIONS_DIR,
        'complete': COMPLETED_MISSIONS_DIR,
        'abandoned': ABANDONED_MISSIONS_DIR
    }
    for status, directory in directories.items():
        for filepath in directory.glob("*.json"):
            data = load_json(filepath)
            if data:
                mission_id = data['id']
                # Keep if newer or not seen
                existing = missions_by_id.get(mission_id)
                if not existing or data.get('updated_at', '') > existing.get('updated_at', ''):
                    missions_by_id[mission_id] = {
                        'id': mission_id,
                        'title': data['title'],
                        'status': data.get('status', status),
                        'tasks': len(data.get('tasks', [])),
                        'created_by': data.get('created_by', ''),
                        'updated_at': data.get('updated_at', ''),
                        '_source': 'local'
                    }

    # 2. Read from all remote branches
    for branch in _get_remote_branches():
        for mission_data in _read_missions_from_branch(branch):
            mission_id = mission_data['id']
            # Keep if newer or not seen
            existing = missions_by_id.get(mission_id)
            if not existing or mission_data.get('updated_at', '') > existing.get('updated_at', ''):
                missions_by_id[mission_id] = {
                    'id': mission_id,
                    'title': mission_data['title'],
                    'status': mission_data.get('status', 'active'),
                    'tasks': len(mission_data.get('tasks', [])),
                    'created_by': mission_data.get('created_by', ''),
                    'updated_at': mission_data.get('updated_at', ''),
                    '_source': branch
                }

    # Filter by status if requested
    missions = list(missions_by_id.values())
    if status_filter:
        missions = [m for m in missions if m['status'] == status_filter]

    return sorted(missions, key=lambda m: m.get('updated_at', ''), reverse=True)


# =============================================================================
# Automated Check Runner
# =============================================================================

def run_check(check: AutomatedCheck) -> tuple[bool, str]:
    """Run an automated check."""
    try:
        result = subprocess.run(
            check.command, shell=True,
            capture_output=True, text=True, timeout=300
        )
        passed = result.returncode == check.expected_exit_code
        output = result.stdout + result.stderr
        return passed, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Check timed out"
    except Exception as e:
        return False, str(e)


# =============================================================================
# Commands
# =============================================================================

def cmd_mission_create(args):
    """Create a new mission."""
    title = " ".join(args.title)

    mission = MissionOnHand(
        id=generate_id("mission"),
        title=title,
        description=getattr(args, 'description', '') or "",
        status=MissionStatus.PLANNING.value,
        created_by=get_identity_name(),
        created_at=now_iso(),
        updated_at=now_iso(),
        strategy=Strategy(
            approach=getattr(args, 'approach', None) or "sequential",
            priority=getattr(args, 'priority', None) or "normal"
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

    print(f"\u2705 Mission created: {mission.id}")
    print(f"   Title: {mission.title}")
    print(f"   Status: {mission.status}")
    if success:
        print(f"   \U0001F4DD Commit: {commit_hash}")
    print(f"   \U0001F4C1 Saved to: {filepath}")


def cmd_mission_list(args):
    """List all missions."""
    status = getattr(args, 'status', None)
    missions = list_missions(status)

    if not missions:
        print("\U0001F4ED No missions found")
        return

    print(f"\n\U0001F4CB Missions ({len(missions)}):")
    print("\u2500" * 70)

    for m in missions:
        status_emoji = {
            'planning': '\U0001F4DD', 'active': '\U0001F525', 'blocked': '\U0001F534',
            'paused': '\u23F8\uFE0F', 'complete': '\u2705', 'abandoned': '\u274C'
        }.get(m['status'], '\u2753')

        print(f"{status_emoji} [{m['id']}] {m['title']}")
        print(f"   Status: {m['status']} | Tasks: {m['tasks']} | By: {m['created_by']}")

    print("\u2500" * 70)


def cmd_mission_show(args):
    """Show mission details."""
    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    print()
    print("=" * 70)
    print(f"\U0001F3AF MISSION: {mission.title}")
    print("=" * 70)
    print(f"ID:          {mission.id}")
    print(f"Status:      {mission.status}")
    print(f"Created by:  {mission.created_by}")
    print(f"Created at:  {mission.created_at[:19]}")

    if mission.description:
        print(f"\nDescription: {mission.description}")

    print("\n\U0001F4CA STRATEGY")
    print("-" * 40)
    print(f"Approach:    {mission.strategy.approach}")
    print(f"Priority:    {mission.strategy.priority}")

    print(f"\n\U0001F4CB TASKS ({len(mission.tasks)})")
    print("-" * 40)
    if mission.tasks:
        for task in mission.tasks:
            emoji = {
                'pending': '\u2B1C', 'ready': '\U0001F7E1', 'in_progress': '\U0001F535',
                'in_review': '\U0001F7E3', 'blocked': '\U0001F534', 'complete': '\u2705', 'skipped': '\u23ED\uFE0F'
            }.get(task.status, '\u2753')
            print(f"  {emoji} [{task.id}] {task.title}")
    else:
        print("  (no tasks yet)")

    bc_checked = sum(1 for item in mission.before_code.items if item.checked)
    print(f"\n\U0001F4DD BEFORE CODE ({bc_checked}/{len(mission.before_code.items)} checked)")

    dod_verified = sum(1 for c in mission.dod.required if c.verified)
    print(f"\u2705 DEFINITION OF DONE ({dod_verified}/{len(mission.dod.required)} verified)")

    print("=" * 70)


def cmd_mission_start(args):
    """Start a mission."""
    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    required_unchecked = [item for item in mission.before_code.items if item.required and not item.checked]

    if required_unchecked and not getattr(args, 'force', False):
        print("\u274C Cannot start mission - beforeCode checklist incomplete:")
        for item in required_unchecked:
            print(f"  \u2B1C {item.description}")
        print("\nComplete the checklist first or use --force")
        sys.exit(1)

    mission.status = MissionStatus.ACTIVE.value
    _, success, commit_hash = save_and_commit(mission, f"mission(start): {mission.id}")

    print(f"\U0001F525 Mission started: {mission.title}")
    if success:
        print(f"   \U0001F4DD Commit: {commit_hash}")


def cmd_mission_complete(args):
    """Mark mission as complete."""
    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    unverified = [c for c in mission.dod.required if not c.verified]

    if unverified and not getattr(args, 'force', False):
        print("\u274C Cannot complete mission - DoD not satisfied:")
        for c in unverified:
            print(f"  \u2B1C {c.description}")
        print("\nVerify all DoD criteria first or use --force")
        sys.exit(1)

    old_path = ACTIVE_MISSIONS_DIR / f"{mission.id}.json"

    mission.status = MissionStatus.COMPLETE.value
    mission.completed_at = now_iso()

    new_path = save_mission(mission)

    if old_path.exists() and old_path != new_path:
        old_path.unlink()
        run_git("add", str(old_path), check=False)

    success, commit_hash, _ = safe_commit(f"mission(complete): {mission.id}", [str(new_path)])

    print(f"\U0001F389 Mission completed: {mission.title}")
    if success:
        print(f"   \U0001F4DD Commit: {commit_hash}")


def cmd_task_add(args):
    """Add a task to a mission."""
    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    task = Task(
        id=generate_id("task"),
        title=" ".join(args.title),
        task_type=getattr(args, 'type', None) or "other",
        description=getattr(args, 'description', None),
        status=TaskStatus.PENDING.value
    )

    mission.tasks.append(task)
    _, success, commit_hash = save_and_commit(mission, f"mission(task): add {task.id} to {mission.id}")

    print(f"\u2705 Task added: {task.id}")
    print(f"   Title: {task.title}")
    if success:
        print(f"   \U0001F4DD Commit: {commit_hash}")


def cmd_task_claim(args):
    """
    Claim a task for work.

    Multi-Agent: Tasks can be claimed independently of phases.
    If a task is already claimed by another agent, this will fail.

    Event-Sourced: Emits a TASK_CLAIMED event instead of modifying the mission file.
    This eliminates merge conflicts when multiple agents claim different tasks.
    """
    from .core import load_identity
    identity = load_identity()
    if not identity:
        print("\u274C No identity. Run: brain init --name <name>")
        sys.exit(1)

    mission = load_mission(args.mission_id)
    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    task = next((t for t in mission.tasks if t.id == args.task_id), None)
    if not task:
        print(f"\u274C Task not found: {args.task_id}")
        sys.exit(1)

    # Check if already claimed by another agent
    if task.claimed_by and task.claimed_by != identity["full_id"]:
        if getattr(args, 'force', False):
            print(f"\u26A0\uFE0F  Force-claiming from {task.claimed_by} (stale claim override)")
        else:
            print(f"\u274C Task already claimed by {task.claimed_by}")
            print("   Use --force to override a stale claim")
            sys.exit(1)

    old_claimer = task.claimed_by if task.claimed_by != identity["full_id"] else None

    # Emit event instead of modifying mission file
    push = getattr(args, 'push', False)
    emit_mission_event(
        event_type=MissionEventType.TASK_CLAIMED,
        mission_id=args.mission_id,
        actor=identity["full_id"],
        data={
            "task_id": args.task_id,
            "task_title": task.title,
            "force": bool(old_claimer),
            "previous_claimer": old_claimer
        },
        push=push
    )

    print(f"\U0001F3AF Task claimed: {task.title}")
    print(f"   Claimed by: {identity['full_id']}")
    print("   \U0001F4DD Event emitted (conflict-free)")


def cmd_task_release(args):
    """
    Release a claimed task.

    Event-Sourced: Emits a TASK_RELEASED event instead of modifying the mission file.
    """
    from .core import load_identity
    identity = load_identity()
    if not identity:
        print("\u274C No identity. Run: brain init --name <name>")
        sys.exit(1)

    mission = load_mission(args.mission_id)
    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    task = next((t for t in mission.tasks if t.id == args.task_id), None)
    if not task:
        print(f"\u274C Task not found: {args.task_id}")
        sys.exit(1)

    # Only the claimer can release (or force)
    if task.claimed_by and task.claimed_by != identity["full_id"] and not getattr(args, 'force', False):
        print(f"\u274C Task claimed by {task.claimed_by}, not you. Use --force to override.")
        sys.exit(1)

    old_claimer = task.claimed_by

    # Emit event instead of modifying mission file
    push = getattr(args, 'push', False)
    emit_mission_event(
        event_type=MissionEventType.TASK_RELEASED,
        mission_id=args.mission_id,
        actor=identity["full_id"],
        data={
            "task_id": args.task_id,
            "task_title": task.title,
            "previous_claimer": old_claimer
        },
        push=push
    )

    print(f"\U0001F513 Task released: {task.title}")
    if old_claimer:
        print(f"   Was claimed by: {old_claimer}")
    print("   \U0001F4DD Event emitted (conflict-free)")


def cmd_task_start(args):
    """
    Start working on a task (must be claimed first or will auto-claim).

    Event-Sourced: Emits TASK_CLAIMED (if needed) and TASK_STARTED events.
    """
    from .core import load_identity
    identity = load_identity()
    if not identity:
        print("\u274C No identity. Run: brain init --name <name>")
        sys.exit(1)

    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    task = next((t for t in mission.tasks if t.id == args.task_id), None)

    if not task:
        print(f"\u274C Task not found: {args.task_id}")
        sys.exit(1)

    push = getattr(args, 'push', False)

    # Auto-claim if not claimed
    if not task.claimed_by:
        emit_mission_event(
            event_type=MissionEventType.TASK_CLAIMED,
            mission_id=args.mission_id,
            actor=identity["full_id"],
            data={"task_id": args.task_id, "task_title": task.title, "auto_claim": True},
            push=False  # Don't push yet, we'll push with start event
        )
        print(f"   Auto-claimed task")
    elif task.claimed_by != identity["full_id"]:
        print(f"\u274C Task claimed by {task.claimed_by}. Claim it first or ask them to release.")
        sys.exit(1)

    # Emit start event
    emit_mission_event(
        event_type=MissionEventType.TASK_STARTED,
        mission_id=args.mission_id,
        actor=identity["full_id"],
        data={"task_id": args.task_id, "task_title": task.title},
        push=push
    )

    print(f"\U0001F535 Task started: {task.title}")
    print("   \U0001F4DD Event emitted (conflict-free)")


def cmd_task_complete(args):
    """
    Mark a task as complete.

    Event-Sourced: Emits a TASK_COMPLETED event instead of modifying the mission file.
    """
    from .core import load_identity
    identity = load_identity()
    if not identity:
        print("\u274C No identity. Run: brain init --name <name>")
        sys.exit(1)

    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    task = next((t for t in mission.tasks if t.id == args.task_id), None)

    if not task:
        print(f"\u274C Task not found: {args.task_id}")
        sys.exit(1)

    # Emit completion event
    push = getattr(args, 'push', False)
    emit_mission_event(
        event_type=MissionEventType.TASK_COMPLETED,
        mission_id=args.mission_id,
        actor=identity["full_id"],
        data={"task_id": args.task_id, "task_title": task.title},
        push=push
    )

    print(f"\u2705 Task completed: {task.title}")
    print("   \U0001F4DD Event emitted (conflict-free)")


def cmd_gate_beforecode(args):
    """Show beforeCode checklist."""
    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    print(f"\n\U0001F4DD BEFORE CODE CHECKLIST - {mission.title}")
    print("-" * 60)

    for item in mission.before_code.items:
        required = "\U0001F534" if item.required else "\u25FD"
        checked = "\u2705" if item.checked else "\u2B1C"
        print(f"  {checked} [{item.id}] {required} {item.description}")
        if item.checked and item.checked_by:
            print(f"      \u2514\u2500 Checked by {item.checked_by}")

    checked_count = sum(1 for item in mission.before_code.items if item.checked)
    print("-" * 60)
    print(f"Progress: {checked_count}/{len(mission.before_code.items)} checked")


def cmd_gate_check(args):
    """
    Check/uncheck a beforeCode item.

    Event-Sourced: Emits a CHECKLIST_CHECKED event instead of modifying the mission file.
    """
    from .core import load_identity
    identity = load_identity()
    if not identity:
        print("\u274C No identity. Run: brain init --name <name>")
        sys.exit(1)

    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    item = next((i for i in mission.before_code.items if i.id == args.item_id), None)

    if not item:
        print(f"\u274C Item not found: {args.item_id}")
        sys.exit(1)

    checked = not getattr(args, 'uncheck', False)

    # Emit event instead of modifying mission file
    push = getattr(args, 'push', False)
    emit_mission_event(
        event_type=MissionEventType.CHECKLIST_CHECKED,
        mission_id=args.mission_id,
        actor=identity["full_id"],
        data={
            "item_id": args.item_id,
            "item_description": item.description,
            "checked": checked
        },
        push=push
    )

    if checked:
        print(f"\u2705 Checked: {item.description}")
    else:
        print(f"\u2B1C Unchecked: {item.description}")

    print("   \U0001F4DD Event emitted (conflict-free)")


def cmd_gate_dod(args):
    """Show Definition of Done."""
    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    print(f"\n\u2705 DEFINITION OF DONE - {mission.title}")
    print("=" * 60)

    print("\n\U0001F534 REQUIRED:")
    for c in mission.dod.required:
        emoji = "\u2705" if c.verified else "\u2B1C"
        print(f"  {emoji} [{c.id}] {c.description}")

    if mission.dod.optional:
        print("\n\u25FD OPTIONAL:")
        for c in mission.dod.optional:
            emoji = "\u2705" if c.verified else "\u25FD"
            print(f"  {emoji} [{c.id}] {c.description}")

    if mission.dod.automated:
        print("\n\U0001F916 AUTOMATED CHECKS:")
        for check in mission.dod.automated:
            result_emoji = {"\u2705": "pass", "\u274C": "fail"}.get(check.last_result, "\u2B1C")
            print(f"  {result_emoji} [{check.id}] {check.description}")

    print("=" * 60)


def cmd_gate_verify(args):
    """
    Verify a DoD criterion.

    Event-Sourced: Emits a DOD_VERIFIED event instead of modifying the mission file.
    """
    from .core import load_identity
    identity = load_identity()
    if not identity:
        print("\u274C No identity. Run: brain init --name <name>")
        sys.exit(1)

    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    criterion = None
    for c in mission.dod.required + mission.dod.optional:
        if c.id == args.criterion_id:
            criterion = c
            break

    if not criterion:
        print(f"\u274C Criterion not found: {args.criterion_id}")
        sys.exit(1)

    evidence = getattr(args, 'evidence', None)

    # Emit event instead of modifying mission file
    push = getattr(args, 'push', False)
    emit_mission_event(
        event_type=MissionEventType.DOD_VERIFIED,
        mission_id=args.mission_id,
        actor=identity["full_id"],
        data={
            "criterion_id": args.criterion_id,
            "criterion_description": criterion.description,
            "evidence": evidence
        },
        push=push
    )

    print(f"\u2705 Verified: {criterion.description}")
    print("   \U0001F4DD Event emitted (conflict-free)")


def cmd_gate_run(args):
    """Run automated DoD checks."""
    mission = load_mission(args.mission_id)

    if not mission:
        print(f"\u274C Mission not found: {args.mission_id}")
        sys.exit(1)

    print(f"\n\U0001F916 Running DoD automated checks for: {mission.title}")
    print("-" * 60)

    all_passed = True

    for check in mission.dod.automated:
        print(f"\n\u25B6\uFE0F  {check.description}")
        print(f"   Command: {check.command}")

        passed, output = run_check(check)

        check.last_run = now_iso()
        check.last_result = "pass" if passed else "fail"

        if passed:
            print("   \u2705 PASSED")
        else:
            print("   \u274C FAILED")
            if output:
                print(f"   Output: {output[:200]}")
            all_passed = False

    _, success, commit_hash = save_and_commit(mission, "mission(dod): run automated checks")

    print("\n" + "-" * 60)
    if success:
        print(f"\U0001F4DD Commit: {commit_hash}")
    if all_passed:
        print("\u2705 All automated checks passed!")
    else:
        print("\u274C Some checks failed")
        sys.exit(1)
