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


class CounterExampleIf(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_fault_localization(self, file: Path) -> list[int]:
        # Create command to run 
        base_dir = gl.BASE_PATH / "build_output/CounterExampleIf"
        pattern = "**/CounterExampleIf"
        exec = _find_executable(base_dir, pattern)
               # run this command and get the output on a variable
        command = [
             exec,
            str(file),
        ]

        (status, stdout, stderr) = run_cmd.run_external_cmd(command)
        if(status != run_cmd.Status.OK):
            # If run cmd finished by any reason with error send empty prediction
            print(command)
            print(status)
            print(stdout)
            print(stderr)

            print("---------------------")
            return []
        
        json_pattern = r"```json\s*(.*?)\s*```"
        matches = re.findall(json_pattern, stdout, re.DOTALL)

        all_results = []
        for json_str in matches:
            try:
                # 2. Parse the string into a Python dictionary
                data = json.loads(json_str)
                all_results.append(data)
            except json.JSONDecodeError as e:
                print(f"Failed to parse a JSON block: {e}")
                continue
        lines: list[int] = []
        
        for result in all_results:
            nodes = result["Nodes"]
            for node in nodes:
                lines.append(node["Line"])

        if(len(lines) == 0):
            print("No lines found in the output, returning empty prediction.")
            print(command)
            print(file)
            print("---------------------")

        return lines
        