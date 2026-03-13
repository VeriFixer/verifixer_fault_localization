from fl_eval.core.abstract import FLTechnique
import fl_eval.util.run_external_cmd as run_cmd
import fl_eval.util.globals as gl
import json
import re
from pathlib import Path

# This will try to find globs like this base_dir/**pattern see other files for more examples
def _find_executable(base_dir : Path, pattern : str) -> Path:
        for path in base_dir.rglob(pattern):
            if path.is_file() and "ref" not in path.parts:
                return path
                    
        raise FileNotFoundError(f"Could not find {pattern} executable in {base_dir}")


class CounterExampleIfReassume(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_fault_localization(self, file: Path) -> list[int]:
        # Create command to run 
        base_dir = gl.BASE_PATH / "build_output/CounterExampleIfReassume"
        pattern = "**/CounterExampleIfReassume"
        exec = _find_executable(base_dir, pattern)
               # run this command and get the output on a variable
        command = [
             exec,
            str(file),
        ]

        (status, stdout, stderr) = run_cmd.run_external_cmd(command)
        if(status != run_cmd.Status.OK):
            # If run cmd finished by any reason with error send empty prediction
            print(
                f"Command crashed\n"
                f"Command : {command}\n"
                f"Status  : {status}\n"
                f"Stdout  : {stdout}\n"
                f"Stderr  : {stderr}\n"
                "---------------------"
            )
            return []

        match = re.search(r"JSON_OUTPUT_START\s*(.*?)\s*JSON_OUTPUT_END", stdout, re.S)
        if not match:
            print(f"JSON output was not found for file {file}")
            return []

        data = json.loads(match.group(1))
        lines : list[int]= []
        for counter_l in data:
             for line in counter_l:
                  if(line not in lines):
                         lines.append(line)
        return lines