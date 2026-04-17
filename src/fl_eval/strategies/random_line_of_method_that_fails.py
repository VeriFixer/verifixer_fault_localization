from fl_eval.core.abstract import FLTechnique
import fl_eval.execution.external_cmd as run_cmd
import config as gl
from pathlib import Path
import re
from typing import Any
from logging_config import get_logger
import random

logger = get_logger(__name__)

def _find_executable(base_dir: Path, pattern: str) -> Path:
    for path in base_dir.rglob(pattern):
        if path.is_file() and "ref" not in path.parts:
            return path
    raise FileNotFoundError(f"Could not find {pattern} executable in {base_dir}")



class RandomLineOfMethodThatFails(FLTechnique):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name)

    def get_fault_localization(self, file: Path) -> list[int]:
        base_dir = gl.BASE_PATH / "build_output/ReturnAtRandomAllLinesOfFailingMethod"
        pattern = "**/ReturnAtRandomAllLinesOfFailingMethod"
        executable = _find_executable(base_dir, pattern)

        command = [
            str(executable),
            str(file),
            "--max-time", str(gl.MAX_TIME_EXTERNAL_PROGRAMS),
            "--max-ram", str(gl.MAX_RAM_EXTERNAL_PROGRAMS),
        ]

        status, stdout, stderr = run_cmd.run_external_cmd(command)
        if status != run_cmd.Status.OK:
            logger.error("Sending empty prediction because of error in execution")
            logger.debug(f"Command: {command}")
            logger.debug(f"Status: {status}")
            logger.debug(f"Stdout: {stdout}")
            logger.debug(f"Stderr: {stderr}")
            logger.debug("-" * 30)
            return []

        match = re.search(r"spans lines (\d+) to (\d+)", stdout)
        if not match:
            raise ValueError(f"Unexpected output format from method extraction binary: {stdout}")

        start_line = int(match.group(1))
        end_line = int(match.group(2))
        l = list(range(start_line, end_line + 1))
        random.shuffle(l)
        return l