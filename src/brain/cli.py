#!/usr/bin/env python3
"""
brain/cli.py - Unified Brain Protocol CLI

Entry point for all brain commands. Follows Open/Closed principle:
- Open for extension (add new command modules)
- Closed for modification (each module handles its own commands)

Usage:
    brain init --name claude
    brain status
    brain msg send "Hello"
    brain phase claim 17
    brain mission create "Title"
    brain gate dod <mission-id>
"""

import argparse
import sys
from pathlib import Path

# Ensure package imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.core import require_project_root
from brain import identity, messaging, phases, missions


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="brain",
        description="Multi-Agent Collaboration Protocol CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Domains:
  Identity:    init, status, keys
  Messaging:   msg send, msg announce, msg listen, msg log
  Phases:      phase claim, phase release, phase complete, phase list
  Coordination: sync, receipt
  Maintenance: reset
  Missions:    mission create, mission list, mission show, mission start
  Tasks:       task add, task start, task complete
  Gates:       gate beforecode, gate check, gate dod, gate verify, gate run

Examples:
  brain init --name claude       Initialize identity
  brain msg send "Hello team"    Send message on branch
  brain phase claim 17           Claim phase 17
  brain mission create "Title"   Create a new mission
  brain gate dod <mission-id>    Show Definition of Done
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command domain")

    # =========================================================================
    # Identity Commands
    # =========================================================================
    p_init = subparsers.add_parser("init", help="Initialize identity")
    p_init.add_argument("--name", "-n", help="Short name (e.g., claude)")
    p_init.add_argument("--reset", "-r", action="store_true", help="Reset identity")

    p_status = subparsers.add_parser("status", help="Show current status")

    p_keys = subparsers.add_parser("keys", help="Manage cryptographic keys")
    p_keys.add_argument("subcommand", nargs="?", default="show",
                        choices=["show", "verify", "regenerate"])
    p_keys.add_argument("target", nargs="?", help="Target identity (for verify)")

    # =========================================================================
    # Messaging Commands (msg domain)
    # =========================================================================
    p_msg = subparsers.add_parser("msg", help="Messaging commands")
    msg_sub = p_msg.add_subparsers(dest="msg_command")

    p_msg_send = msg_sub.add_parser("send", help="Send message on branch")
    p_msg_send.add_argument("message", nargs="+", help="Message to send")
    p_msg_send.add_argument("--push", "-p", action="store_true", help="Push after commit")

    p_msg_announce = msg_sub.add_parser("announce", help="Broadcast to all agents")
    p_msg_announce.add_argument("message", nargs="+", help="Message to announce")

    p_msg_listen = msg_sub.add_parser("listen", help="Listen for announcements")
    p_msg_listen.add_argument("--limit", "-n", type=int, default=20)

    p_msg_log = msg_sub.add_parser("log", help="Show local event log")
    p_msg_log.add_argument("--limit", "-n", type=int, default=20)

    # =========================================================================
    # Phase Commands (phase domain)
    # =========================================================================
    p_phase = subparsers.add_parser("phase", help="Phase coordination")
    phase_sub = p_phase.add_subparsers(dest="phase_command")

    p_phase_claim = phase_sub.add_parser("claim", help="Claim a phase")
    p_phase_claim.add_argument("phase", type=int, help="Phase number")
    p_phase_claim.add_argument("--push", "-p", action="store_true")

    p_phase_release = phase_sub.add_parser("release", help="Release a phase")
    p_phase_release.add_argument("phase", type=int, help="Phase number")
    p_phase_release.add_argument("--reason", "-r", help="Reason for release")
    p_phase_release.add_argument("--push", "-p", action="store_true")

    p_phase_complete = phase_sub.add_parser("complete", help="Complete a phase")
    p_phase_complete.add_argument("phase", type=int, help="Phase number")
    p_phase_complete.add_argument("pr", help="PR number or URL")
    p_phase_complete.add_argument("--push", "-p", action="store_true")

    p_phase_list = phase_sub.add_parser("list", help="List all phases")

    # =========================================================================
    # Coordination Commands
    # =========================================================================
    p_sync = subparsers.add_parser("sync", help="Sync with remote branches")

    p_receipt = subparsers.add_parser("receipt", help="Post read receipt")
    p_receipt.add_argument("--push", "-p", action="store_true")

    # =========================================================================
    # Reset Command
    # =========================================================================
    p_reset = subparsers.add_parser("reset", help="Reset brain state")
    p_reset.add_argument("--force", "-f", action="store_true",
                         help="Required to confirm reset")
    p_reset.add_argument("--dry-run", action="store_true",
                         help="Show what would be reset without doing it")
    p_reset.add_argument("--all", action="store_true",
                         help="Reset everything (default if no target specified)")
    p_reset.add_argument("--soft", action="store_true",
                         help="Reset state but keep identity")
    p_reset.add_argument("--identity", action="store_true",
                         help="Reset identity only")
    p_reset.add_argument("--events", action="store_true",
                         help="Reset events log only")
    p_reset.add_argument("--claims", action="store_true",
                         help="Reset claims only")
    p_reset.add_argument("--missions", action="store_true",
                         help="Reset missions only")
    p_reset.add_argument("--messages", action="store_true",
                         help="Reset messages only")
    p_reset.add_argument("--receipts", action="store_true",
                         help="Reset receipts only")
    p_reset.add_argument("--keys", action="store_true",
                         help="Reset keys only")

    # =========================================================================
    # Mission Commands (mission domain)
    # =========================================================================
    p_mission = subparsers.add_parser("mission", help="Mission management")
    mission_sub = p_mission.add_subparsers(dest="mission_command")

    p_mission_create = mission_sub.add_parser("create", help="Create mission")
    p_mission_create.add_argument("title", nargs="+", help="Mission title")
    p_mission_create.add_argument("--description", "-d", help="Description")
    p_mission_create.add_argument("--approach", choices=["sequential", "parallel", "hybrid"])
    p_mission_create.add_argument("--priority", choices=["critical", "high", "normal", "low"])
    p_mission_create.add_argument("--push", "-p", action="store_true")

    p_mission_list = mission_sub.add_parser("list", help="List missions")
    p_mission_list.add_argument("--status", choices=["active", "complete", "abandoned"])

    p_mission_show = mission_sub.add_parser("show", help="Show mission details")
    p_mission_show.add_argument("mission_id", help="Mission ID")

    p_mission_start = mission_sub.add_parser("start", help="Start a mission")
    p_mission_start.add_argument("mission_id", help="Mission ID")
    p_mission_start.add_argument("--force", "-f", action="store_true")

    p_mission_complete = mission_sub.add_parser("complete", help="Complete a mission")
    p_mission_complete.add_argument("mission_id", help="Mission ID")
    p_mission_complete.add_argument("--force", "-f", action="store_true")

    # =========================================================================
    # Task Commands (task domain)
    # =========================================================================
    p_task = subparsers.add_parser("task", help="Task management")
    task_sub = p_task.add_subparsers(dest="task_command")

    p_task_add = task_sub.add_parser("add", help="Add a task")
    p_task_add.add_argument("mission_id", help="Mission ID")
    p_task_add.add_argument("title", nargs="+", help="Task title")
    p_task_add.add_argument("--type", choices=["phase", "bugfix", "feature", "refactor", "docs", "test", "other"])
    p_task_add.add_argument("--description", "-d", help="Description")

    p_task_claim = task_sub.add_parser("claim", help="Claim a task (multi-agent)")
    p_task_claim.add_argument("mission_id", help="Mission ID")
    p_task_claim.add_argument("task_id", help="Task ID")
    p_task_claim.add_argument("--force", "-f", action="store_true", help="Override stale claim")

    p_task_release = task_sub.add_parser("release", help="Release a claimed task")
    p_task_release.add_argument("mission_id", help="Mission ID")
    p_task_release.add_argument("task_id", help="Task ID")
    p_task_release.add_argument("--force", "-f", action="store_true", help="Force release even if not your claim")

    p_task_start = task_sub.add_parser("start", help="Start a task (auto-claims if not claimed)")
    p_task_start.add_argument("mission_id", help="Mission ID")
    p_task_start.add_argument("task_id", help="Task ID")

    p_task_complete = task_sub.add_parser("complete", help="Complete a task")
    p_task_complete.add_argument("mission_id", help="Mission ID")
    p_task_complete.add_argument("task_id", help="Task ID")

    # =========================================================================
    # Gate Commands (gate domain - quality gates)
    # =========================================================================
    p_gate = subparsers.add_parser("gate", help="Quality gates (beforeCode, DoD)")
    gate_sub = p_gate.add_subparsers(dest="gate_command")

    p_gate_beforecode = gate_sub.add_parser("beforecode", help="Show beforeCode checklist")
    p_gate_beforecode.add_argument("mission_id", help="Mission ID")

    p_gate_check = gate_sub.add_parser("check", help="Check a beforeCode item")
    p_gate_check.add_argument("mission_id", help="Mission ID")
    p_gate_check.add_argument("item_id", help="Item ID")
    p_gate_check.add_argument("--uncheck", "-u", action="store_true")

    p_gate_dod = gate_sub.add_parser("dod", help="Show Definition of Done")
    p_gate_dod.add_argument("mission_id", help="Mission ID")

    p_gate_verify = gate_sub.add_parser("verify", help="Verify a DoD criterion")
    p_gate_verify.add_argument("mission_id", help="Mission ID")
    p_gate_verify.add_argument("criterion_id", help="Criterion ID")
    p_gate_verify.add_argument("--evidence", "-e", help="Link to evidence")

    p_gate_run = gate_sub.add_parser("run", help="Run automated checks")
    p_gate_run.add_argument("mission_id", help="Mission ID")

    return parser


def main():
    """Main entry point."""
    require_project_root()

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to appropriate module
    cmd = args.command

    # Identity commands
    if cmd == "init":
        identity.cmd_init(args)
    elif cmd == "status":
        identity.cmd_status(args)
    elif cmd == "keys":
        identity.cmd_keys(args)

    # Messaging commands
    elif cmd == "msg":
        if args.msg_command == "send":
            messaging.cmd_send(args)
        elif args.msg_command == "announce":
            messaging.cmd_announce(args)
        elif args.msg_command == "listen":
            messaging.cmd_listen(args)
        elif args.msg_command == "log":
            messaging.cmd_log(args)
        else:
            parser.parse_args(["msg", "--help"])

    # Phase commands
    elif cmd == "phase":
        if args.phase_command == "claim":
            phases.cmd_claim(args)
        elif args.phase_command == "release":
            phases.cmd_release(args)
        elif args.phase_command == "complete":
            phases.cmd_complete(args)
        elif args.phase_command == "list":
            phases.cmd_phases(args)
        else:
            parser.parse_args(["phase", "--help"])

    # Coordination commands
    elif cmd == "sync":
        phases.cmd_sync(args)
    elif cmd == "receipt":
        phases.cmd_receipt(args)

    # Reset command
    elif cmd == "reset":
        from brain import maintenance
        maintenance.cmd_reset(args)

    # Mission commands
    elif cmd == "mission":
        if args.mission_command == "create":
            missions.cmd_mission_create(args)
        elif args.mission_command == "list":
            missions.cmd_mission_list(args)
        elif args.mission_command == "show":
            missions.cmd_mission_show(args)
        elif args.mission_command == "start":
            missions.cmd_mission_start(args)
        elif args.mission_command == "complete":
            missions.cmd_mission_complete(args)
        else:
            parser.parse_args(["mission", "--help"])

    # Task commands
    elif cmd == "task":
        if args.task_command == "add":
            missions.cmd_task_add(args)
        elif args.task_command == "claim":
            missions.cmd_task_claim(args)
        elif args.task_command == "release":
            missions.cmd_task_release(args)
        elif args.task_command == "start":
            missions.cmd_task_start(args)
        elif args.task_command == "complete":
            missions.cmd_task_complete(args)
        else:
            parser.parse_args(["task", "--help"])

    # Gate commands
    elif cmd == "gate":
        if args.gate_command == "beforecode":
            missions.cmd_gate_beforecode(args)
        elif args.gate_command == "check":
            missions.cmd_gate_check(args)
        elif args.gate_command == "dod":
            missions.cmd_gate_dod(args)
        elif args.gate_command == "verify":
            missions.cmd_gate_verify(args)
        elif args.gate_command == "run":
            missions.cmd_gate_run(args)
        else:
            parser.parse_args(["gate", "--help"])

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
