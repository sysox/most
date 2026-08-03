"""Generic CLI adapter with process-group/job isolation semantics."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CLIExecution:
    process: subprocess.Popen[str]
    command: tuple[str, ...]
    working_directory: str


@dataclass(frozen=True, slots=True)
class CancellationReport:
    requested: bool
    forced: bool
    returncode: int | None


class CLIAdapter:
    adapter_type = "cli"

    def start(self, executable: str, arguments: list[str], working_directory: Path,
              environment: dict[str, str] | None = None) -> CLIExecution:
        if not working_directory.is_dir():
            raise ValueError("CLI working directory must exist")
        kwargs: dict[str, object] = {
            "cwd": working_directory,
            "env": environment,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen([executable, *arguments], **kwargs)  # type: ignore[arg-type]
        return CLIExecution(process, tuple([executable, *arguments]), str(working_directory))

    def cancel(self, execution: CLIExecution, grace_seconds: float = 5.0) -> CancellationReport:
        process = execution.process
        if process.poll() is not None:
            return CancellationReport(False, False, process.returncode)
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=grace_seconds)
            return CancellationReport(True, False, process.returncode)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return CancellationReport(True, True, process.returncode)

    def collect(self, execution: CLIExecution) -> tuple[str, str, int]:
        stdout, stderr = execution.process.communicate()
        return stdout, stderr, execution.process.returncode or 0
