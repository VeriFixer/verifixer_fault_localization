import config as gl
import subprocess
from enum import Enum

class Status(Enum):
    OK = 0
    TIMEOUT = 1
    MEMORY_ERROR = 2
    SYSTEMD_LAUNCH_ERROR = 3
    ERROR_EXIT_CODE = 4

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
        return Status.TIMEOUT, "", f"\nCommand timed out: {e}"
    
    except Exception as e:
        # This is for *real* execution failures (systemd-run not found, etc.)
        return Status.SYSTEMD_LAUNCH_ERROR, "", f"\nCommand failed to launch: {e}"

    stdout = result.stdout
    stderr = result.stderr
    rc = result.returncode

    if(len(stderr) > 0):
        if "timed out" in stderr.lower():
            return Status.TIMEOUT, stdout, stderr
        if "memory" in stderr.lower() or "oom" in stderr.lower() or "out of memory" in stderr.lower():
            return Status.MEMORY_ERROR, stdout, stderr

    if(rc != 0):
        return Status.ERROR_EXIT_CODE, stdout, stderr
    
    return Status.OK, stdout, stderr
