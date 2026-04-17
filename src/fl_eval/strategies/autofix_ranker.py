from pathlib import Path
from typing import Any
import tempfile

from fl_eval.core.abstract import FLTechnique
import config as gl
import fl_eval.execution.external_cmd as run_cmd


class AutoFixRanker(FLTechnique):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.autofix_strategy = kwargs.get("autofix_strategy", "dynamic-and-static-score")
        if self.autofix_strategy not in {"dynamic-and-static-score", "dynamic-score-only"}:
            raise ValueError(
                "autofix_strategy must be one of: dynamic-and-static-score, dynamic-score-only"
            )

        self.run_script = gl.AUTOFIX_SCRIPT
        self.output_root = gl.AUTOFIX_RUNS_DIR

    def _parse_ranked_lines(self, lines_file: Path) -> list[int]:
        ranked_lines: list[int] = []
        if not lines_file.is_file():
            return ranked_lines

        with lines_file.open("r", encoding="utf-8") as f:
            for raw_line in f:
                value = raw_line.strip().split(",")[0]
                if not value:
                    continue
                try:
                    line_no = int(value)
                except ValueError:
                    continue
                if line_no not in ranked_lines:
                    ranked_lines.append(line_no)
        return ranked_lines

    def get_fault_localization(self, file: Path) -> list[int]:
        if not self.run_script.is_file():
            print(f"AutoFix runner not found: {self.run_script}")
            return []

        self.output_root.mkdir(parents=True, exist_ok=True)
        run_out_dir = Path(tempfile.mkdtemp(prefix="autofix_", dir=str(self.output_root))) / file.stem
        run_out_dir.mkdir(parents=True, exist_ok=True)

        # Things autofix is apllied to the file with name .test.dfy and not the .dfy file, so we need to adjust the path accordingly.
        file_test = file.with_suffix(".test.dfy")
        if not file_test.is_file():
            print(f"AutoFix input file not found: {file_test}")
            return []

        command: list[str] = [
            "bash",
            str(self.run_script),
            str(file_test),
            "--strategy",
            self.autofix_strategy,
            "--out-dir",
            str(run_out_dir),
        ]

        status, stdout, stderr = run_cmd.run_external_cmd(command, timeout=gl.MAX_TIME_AUTOFIX)
        if status != run_cmd.Status.OK:
            print(
                f"AutoFix command crashed\n"
                f"Command : {" ".join(command)}\n"
                f"Status  : {status}\n"
                f"Stdout  : {stdout}\n"
                f"Stderr  : {stderr}\n"
                "---------------------"
            )
            return []

        result_file = run_out_dir / "lines-suspiciousness.csv"
        ranked_lines = self._parse_ranked_lines(result_file)

        if not ranked_lines:
            print(f"No lines found in AutoFix output for file {file}")
            print(f"Expected output file: {result_file}")
            print("---------------------")

        return ranked_lines
