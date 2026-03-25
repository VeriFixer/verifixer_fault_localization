import config as gl
import subprocess
from enum import Enum
from datetime import datetime, timezone
from typing import Any

class Status(Enum):
    OK = 0
    TIMEOUT = 1
    MEMORY_ERROR = 2
    SYSTEMD_LAUNCH_ERROR = 3
    ERROR_EXIT_CODE = 4


_LAST_EXECUTION_METADATA: dict[str, Any] | None = None


def _record_last_execution(
    cmd: list[str],
    status: Status,
    stdout: str,
    stderr: str,
    return_code: int | None,
) -> None:
    global _LAST_EXECUTION_METADATA
    _LAST_EXECUTION_METADATA = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "command": cmd,
        "status": status.name,
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
    }


def get_last_execution_metadata() -> dict[str, Any] | None:
    if _LAST_EXECUTION_METADATA is None:
        return None
    return dict(_LAST_EXECUTION_METADATA)

def run_external_cmd(cmd: list[str]) -> tuple[Status, str, str]:
    systemd_cmd: list[str] = cmd

    try:
        result = subprocess.run(
            systemd_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=gl.MAX_TIME_EXTERNAL_PROGRAMS + 10
        )
    except subprocess.TimeoutExpired as e:
        status = Status.TIMEOUT
        stdout = ""
        stderr = f"\nCommand timed out: {e}"
        _record_last_execution(cmd, status, stdout, stderr, None)
        return status, stdout, stderr
    
    except Exception as e:
        # This is for *real* execution failures (systemd-run not found, etc.)
        status = Status.SYSTEMD_LAUNCH_ERROR
        stdout = ""
        stderr = f"\nCommand failed to launch: {e}"
        _record_last_execution(cmd, status, stdout, stderr, None)
        return status, stdout, stderr

    stdout = result.stdout
    stderr = result.stderr
    rc = result.returncode

    if(len(stderr) > 0):
        if "timed out" in stderr.lower():
            status = Status.TIMEOUT
            _record_last_execution(cmd, status, stdout, stderr, rc)
            return status, stdout, stderr
        if "memory" in stderr.lower() or "oom" in stderr.lower() or "out of memory" in stderr.lower():
            status = Status.MEMORY_ERROR
            _record_last_execution(cmd, status, stdout, stderr, rc)
            return status, stdout, stderr

    if(rc != 0):
        status = Status.ERROR_EXIT_CODE
        _record_last_execution(cmd, status, stdout, stderr, rc)
        return status, stdout, stderr
    
    status = Status.OK
    _record_last_execution(cmd, status, stdout, stderr, rc)
    return status, stdout, stderr
