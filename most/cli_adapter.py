"""Generic CLI adapter with process-group/job isolation semantics."""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import Connectivity, Observability
from .redaction import redact_text


@dataclass(frozen=True, slots=True)
class CLIExecution:
    process: subprocess.Popen[str]
    command: tuple[str, ...]
    working_directory: str
    job_handle: Any = None

    @property
    def redacted_command(self) -> tuple[str, ...]:
        return redact_command(self.command)


@dataclass(frozen=True, slots=True)
class CancellationReport:
    requested: bool
    forced: bool
    returncode: int | None
    workspace_changed: bool | None = None


class CLIAdapter:
    adapter_type = "cli"

    def validate_configuration(self, configuration: dict[str, Any]) -> list[str]:
        options = configuration.get("adapter_options", {})
        errors = []
        if not options.get("executable"):
            errors.append("adapter_options.executable is required")
        if not options.get("working_directory"):
            errors.append("adapter_options.working_directory is required")
        return errors

    def get_observability_profile(self, configuration: dict[str, Any]) -> Observability:
        return Observability.TEXT_STREAM

    def resolve_connectivity(self, configuration: dict[str, Any]) -> Connectivity:
        return Connectivity(None, "local", "localhost", "DECLARED", ("CLI process is locally launched",))

    def execute(self, request: dict[str, Any], configuration: dict[str, Any], credential: str | None = None) -> dict[str, Any]:
        errors = self.validate_configuration(configuration)
        if errors:
            raise ValueError("invalid CLI configuration: " + "; ".join(errors))
        options = configuration["adapter_options"]
        arguments = [str(argument) for argument in options.get("arguments", [])]
        if credential:
            # The credential may only be passed through an explicitly named
            # environment variable; it is never written to observed arguments.
            environment = os.environ.copy()
            environment.update({str(key): str(value) for key, value in options.get("environment", {}).items()})
            credential_variables = options.get("credential_env_vars") or [options.get("credential_env_var", "MOST_CREDENTIAL")]
            for variable in credential_variables:
                environment[str(variable)] = credential
        else:
            configured_environment = options.get("environment", {})
            if configured_environment:
                environment = os.environ.copy()
                environment.update({str(key): str(value) for key, value in configured_environment.items()})
            else:
                environment = None
        execution = self.start(str(options["executable"]), arguments, Path(str(options["working_directory"])), environment)
        stdout, stderr, returncode = self.collect(execution, (credential,) if credential else ())
        return {"stdout": stdout, "stderr": stderr, "returncode": returncode, "command": execution.redacted_command}

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
        if os.name != "nt":
            kwargs["start_new_session"] = True
        process = subprocess.Popen([executable, *arguments], **kwargs)  # type: ignore[arg-type]
        job_handle = _create_windows_job(process) if os.name == "nt" else None
        return CLIExecution(process, (executable, *arguments), str(working_directory), job_handle)

    def cancel(self, execution: CLIExecution, grace_seconds: float = 5.0,
               workspace_scanner: Callable[[], object] | None = None,
               expected_workspace_state: object | None = None) -> CancellationReport:
        process = execution.process
        if process.poll() is not None:
            return CancellationReport(False, False, process.returncode)
        if os.name == "nt":
            # GenerateConsoleCtrlEvent broadcasts on the console shared with
            # the parent; it has been observed to also strike unrelated
            # sibling processes and the orchestrating process itself, not
            # only the targeted process group. Terminate through the Job
            # Object instead, which isolates the descendant tree without any
            # console-wide signal.
            _terminate_windows_job(execution.job_handle, process)
            process.wait()
            _close_windows_job(execution.job_handle)
            changed = _workspace_changed(workspace_scanner, expected_workspace_state)
            return CancellationReport(True, True, process.returncode, changed)
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=grace_seconds)
            changed = _workspace_changed(workspace_scanner, expected_workspace_state)
            return CancellationReport(True, False, process.returncode, changed)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            changed = _workspace_changed(workspace_scanner, expected_workspace_state)
            return CancellationReport(True, True, process.returncode, changed)

    def collect(self, execution: CLIExecution, secret_values: tuple[str, ...] = ()) -> tuple[str, str, int]:
        stdout, stderr = execution.process.communicate()
        _close_windows_job(execution.job_handle)
        return redact_text(stdout, secret_values), redact_text(stderr, secret_values), execution.process.returncode or 0


def _create_windows_job(process: subprocess.Popen[str]):
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
    process_handle = wintypes.HANDLE(process._handle)
    if not kernel32.AssignProcessToJobObject(handle, process_handle):
        kernel32.CloseHandle(handle)
        raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]
    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimitInformation), ("IoInfo", IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
    limits = ExtendedLimitInformation()
    limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        kernel32.CloseHandle(handle)
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
    # The Job Object is retained for forced cancellation; closing it after
    # cancellation kills descendants when the process is still attached.
    return handle


def _terminate_windows_job(handle, process) -> None:
    if os.name != "nt" or handle is None:
        process.kill()
        return
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.TerminateJobObject(handle, 1):
        process.kill()


def _close_windows_job(handle) -> None:
    if os.name == "nt" and handle is not None:
        import ctypes
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)


def redact_command(command: tuple[str, ...], sensitive_flags: frozenset[str] = frozenset({"--api-key", "--token", "--password", "--secret"})) -> tuple[str, ...]:
    redacted: list[str] = []
    mask_next = False
    for argument in command:
        if mask_next:
            redacted.append("<redacted>")
            mask_next = False
        elif argument in sensitive_flags:
            redacted.append(argument)
            mask_next = True
        elif any(argument.startswith(f"{flag}=") for flag in sensitive_flags):
            redacted.append(argument.split("=", 1)[0] + "=<redacted>")
        else:
            redacted.append(argument)
    return tuple(redacted)


def _workspace_changed(scanner: Callable[[], object] | None, expected: object | None) -> bool | None:
    if scanner is None:
        return None
    current = scanner()
    return expected is not None and current != expected
