"""Generic CLI adapter with process-group/job isolation semantics."""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CLIExecution:
    process: subprocess.Popen[str]
    command: tuple[str, ...]
    working_directory: str
    job_handle: Any = None


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
        job_handle = _create_windows_job(process) if os.name == "nt" else None
        return CLIExecution(process, (executable, *arguments), str(working_directory), job_handle)

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
                _terminate_windows_job(execution.job_handle, process)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            _close_windows_job(execution.job_handle)
            return CancellationReport(True, True, process.returncode)

    def collect(self, execution: CLIExecution) -> tuple[str, str, int]:
        stdout, stderr = execution.process.communicate()
        _close_windows_job(execution.job_handle)
        return stdout, stderr, execution.process.returncode or 0


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
