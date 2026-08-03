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
    configuration.add_argument("--provider", default="")
    configuration.add_argument("--access-method", default="openai-compatible")
    subparsers.add_parser("list-sessions")
    subparsers.add_parser("list-configurations")
    workspace = subparsers.add_parser("inspect-workspace")
    workspace.add_argument("repository", type=Path)
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
        print(json.dumps(WorkspaceService(args.data_root, args.repository).inspect(), indent=2, default=str))
        return 0
    return 2
