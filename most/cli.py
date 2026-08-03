from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import AIConfiguration, SessionMode
from .services import ConfigurationService, SessionService
from .workspace import WorkspaceService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="most", description="File-backed multi-provider AI core")
    parser.add_argument("--data-root", type=Path, default=Path("application-data"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    session = subparsers.add_parser("create-session")
    session.add_argument("title")
    session.add_argument("--workspace", action="store_true")
    configuration = subparsers.add_parser("create-configuration")
    configuration.add_argument("name")
    configuration.add_argument("--provider", default="custom")
    configuration.add_argument("--access-method", default="openai-compatible")
    subparsers.add_parser("list-sessions")
    subparsers.add_parser("list-configurations")
    execution = subparsers.add_parser("inspect-execution")
    execution.add_argument("execution_id")
    workspace = subparsers.add_parser("inspect-workspace")
    workspace.add_argument("repository", type=Path)
    workspace.add_argument("--diff", action="store_true")
    workspace.add_argument("--compatibility", action="store_true")
    workspace.add_argument("--history", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create-session":
        mode = SessionMode.WORKSPACE if args.workspace else SessionMode.COMMUNICATION
        session = SessionService(args.data_root).create(args.title, mode)
        print(session.id)
        return 0
    if args.command == "create-configuration":
        configuration = AIConfiguration(name=args.name, provider_id=args.provider, access_method_id=args.access_method)
        ConfigurationService(args.data_root).save(configuration)
        print(configuration.id)
        return 0
    if args.command == "list-sessions":
        print(json.dumps(SessionService(args.data_root).list(), indent=2, default=str))
        return 0
    if args.command == "list-configurations":
        print(json.dumps(ConfigurationService(args.data_root).list(), indent=2, default=str))
        return 0
    if args.command == "inspect-workspace":
        service = WorkspaceService(args.data_root, args.repository)
        result = service.compatibility_report() if args.compatibility else service.inspect()
        if args.diff and result["is_repository"]:
            result["diff"] = service.git.diff()
        if args.history:
            result["history"] = service.history()
        print(json.dumps(result, indent=2, default=str))
        return 0
    if args.command == "inspect-execution":
        execution_root = args.data_root / "executions"
        direct_metadata = execution_root / args.execution_id / "metadata.yaml"
        direct_events = execution_root / args.execution_id / "events.jsonl"
        metadata = direct_metadata if direct_metadata.exists() else next(execution_root.glob(f"*/{args.execution_id}/metadata.yaml"), None)
        events = direct_events if direct_events.exists() else next(execution_root.glob(f"*/{args.execution_id}/events.jsonl"), None)
        if metadata is None:
            raise SystemExit(f"execution not found: {args.execution_id}")
        import yaml
        result = {"metadata": yaml.safe_load(metadata.read_text(encoding="utf-8"))}
        result["events"] = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()] if events else []
        print(json.dumps(result, indent=2, default=str))
        return 0
    return 2
