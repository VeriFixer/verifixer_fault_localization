from fl_eval.core.abstract import FLTechnique
import fl_eval.util.run_external_cmd as run_cmd
import fl_eval.util.globals as gl
from pathlib import Path
import re
from typing import Any


# This will try to find globs like this base_dir/**pattern see other files for more examples
def _find_executable(base_dir : Path, pattern : str) -> Path:
        for path in base_dir.rglob(pattern):
            if path.is_file() and "ref" not in path.parts:
                return path
        raise FileNotFoundError(f"Could not find {pattern} executable in {base_dir}")

class RandomLineOfMethodThatFails(FLTechnique):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name)

    def get_fault_localization(self, file: Path) -> list[int]:
        # Create command to run 
        base_dir = gl.BASE_PATH / "build_output/ReturnAtRandomAllLinesOfFailingMethod"
        pattern = "**/ReturnAtRandomAllLinesOfFailingMethod"
        exec = _find_executable(base_dir, pattern)
               # run this command and get the output on a variable
        command = [
             str(exec),
            str(file),
            "--max-time", str(gl.MAX_TIME_EXTERNAL_PROGRAMS),
            "--max-ram", str(gl.MAX_RAM_EXTERNAL_PROGRAMS)
        ]

        (status, stdout, stderr) = run_cmd.run_external_cmd(command)
        if(status != run_cmd.Status.OK):
            # If run cmd finished by any reason with error send empty prediction
            print("Sending empty prediciton because of error in execution")
            print(command)
            print(status)
            print(stdout)
            print(stderr)

            print("---------------------")
            return []

        match = re.search(r"spans lines (\d+) to (\d+)", stdout)
        if match:
            start_line = int(match.group(1))
            end_line = int(match.group(2))
            line_numbers = list(range(start_line, end_line + 1))
            # Not ranodm random was worse
            #random.shuffle(line_numbers)
            return line_numbers
        else:
            # NOTE Dany printing creates variables with underscores at the beginning that cannot be
            # Parsed using dafny verify, see example on pos_mutation/killed/BinaryAddition__3122_LVR_0.dfy 
            # The only way to solve it is to rename variables beginning with underscore
            return [] 