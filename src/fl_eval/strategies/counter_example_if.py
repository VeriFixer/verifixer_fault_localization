from fl_eval.core.abstract import FLTechnique
import fl_eval.util.run_external_cmd as run_cmd
import config as gl
from pathlib import Path
from typing import Any

from fl_eval.util.counterexample_trace_utils import parse_counterexample_trace_report, rank_counterexample_nodes
from fl_eval.util.ranking_strategy import (
    DEFAULT_COUNTEREXAMPLE_RANKING_CONTROLS,
    CounterExampleRankingControls,
    RankingStrategy,
    RANK_BY_FREQUENCY,
)


def _find_executable(base_dir: Path, pattern: str) -> Path:
    for path in base_dir.rglob(pattern):
        if path.is_file() and "ref" not in path.parts:
            return path

    raise FileNotFoundError(f"Could not find {pattern} executable in {base_dir}")


class CounterExampleIf(FLTechnique):
    def __init__(
        self,
        name: str,
        ranking_strategy: RankingStrategy = RANK_BY_FREQUENCY,
        ranking_controls: CounterExampleRankingControls = DEFAULT_COUNTEREXAMPLE_RANKING_CONTROLS,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.ranking_strategy = ranking_strategy
        self.ranking_controls = ranking_controls

    @staticmethod
    def _parse_output(stdout: str) -> list[Any]:
        report = parse_counterexample_trace_report(stdout)
        if report is None:
            raise ValueError("CounterExampleIf output missing JSON_OUTPUT_START/JSON_OUTPUT_END markers")

        return report.traces

    def get_fault_localization(self, file: Path) -> list[int]:
        base_dir = gl.BASE_PATH / "build_output/CounterExampleIf"
        executable = _find_executable(base_dir, "**/CounterExampleIf")
        command: list[str] = [
            str(executable),
            str(file),
            "--max-time", str(gl.MAX_TIME_EXTERNAL_PROGRAMS),
            "--max-ram", str(gl.MAX_RAM_EXTERNAL_PROGRAMS),
        ]

        status, stdout, stderr = run_cmd.run_external_cmd(command)
        try:
            parsed_nodes = self._parse_output(stdout)
        except Exception as e:
            print(
                f"Command crashed\n"
                f"Command : {' '.join(command)}\n"
                f"Status  : {status}\n"
                f"Stdout  : {stdout}\n"
                f"Stderr  : {stderr}\n"
                "---------------------"
            )
            print(f"Failed to parse CounterExampleIf output for file {file}: {e}")
            return []

        if not parsed_nodes:
            return []

        return rank_counterexample_nodes(
            parsed_nodes,
            self.ranking_strategy,
            ranking_controls=self.ranking_controls,
        )
