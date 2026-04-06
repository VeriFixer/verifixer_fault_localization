from fl_eval.core.abstract import FLTechnique
import fl_eval.util.run_external_cmd as run_cmd
import config as gl
import json
import re
from pathlib import Path
from typing import Any
from collections import Counter
from fl_eval.util.ranking_strategy import (
    CounterExampleNode,
    RankingStrategy,
    RANK_BY_FREQUENCY,
    RANK_BY_DEPTH_DEEPER_FIRST,
    RANK_BY_ORDER,
    SUPPORTED_RANKING_STRATEGIES,
)

# This will try to find globs like this base_dir/**pattern see other files for more examples
def _find_executable(base_dir : Path, pattern : str) -> Path:
        for path in base_dir.rglob(pattern):
            if path.is_file() and "ref" not in path.parts:
                return path
                    
        raise FileNotFoundError(f"Could not find {pattern} executable in {base_dir}")


class CounterExampleIfReassume(FLTechnique):
    def __init__(
        self,
        name: str,
        ranking_strategy: RankingStrategy = RANK_BY_FREQUENCY,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.ranking_strategy = ranking_strategy

    def _rank_lines(
        self,
        nodes: list[CounterExampleNode],
    ) -> list[int]:
        """Rank lines by suspiciousness using configured strategy."""
        unique_lines: list[int] = []
        for node in nodes:
            if node.line not in unique_lines:
                unique_lines.append(node.line)
        
        if self.ranking_strategy == RANK_BY_FREQUENCY:
            line_counts = Counter(node.line for node in nodes)
            ranked = sorted(unique_lines, key=lambda l: (-line_counts.get(l, 1), unique_lines.index(l)))
            return ranked
        elif self.ranking_strategy == RANK_BY_DEPTH_DEEPER_FIRST:
            line_counts = Counter(node.line for node in nodes)
            max_depth_by_line: dict[int, int] = {}
            for node in nodes:
                max_depth_by_line[node.line] = max(max_depth_by_line.get(node.line, 0), node.depth)
            ranked = sorted(
                unique_lines,
                key=lambda l: (
                    -line_counts.get(l, 1),
                    -max_depth_by_line.get(l, 0),
                    unique_lines.index(l),
                ),
            )
            return ranked
        elif self.ranking_strategy == RANK_BY_ORDER:
            return unique_lines
        else:
            raise ValueError(
                f"Unknown ranking strategy '{self.ranking_strategy}'. "
                f"Supported: {[s.name for s in SUPPORTED_RANKING_STRATEGIES]}"
            )

    @staticmethod
    def _parse_output(stdout: str) -> list[CounterExampleNode]:
        match = re.search(r"JSON_OUTPUT_START\s*(.*?)\s*JSON_OUTPUT_END", stdout, re.S)
        if not match:
            raise ValueError("CounterExampleIfReassume output missing JSON_OUTPUT_START/JSON_OUTPUT_END markers")

        payload = json.loads(match.group(1))
        traces = payload.get("traces")
        if not isinstance(traces, list):
            raise ValueError("CounterExampleIfReassume output missing 'traces' array")

        nodes: list[CounterExampleNode] = []
        for trace in traces:
            trace_id = trace.get("trace_id", 0)
            trace_nodes = trace.get("nodes", [])
            if not isinstance(trace_nodes, list):
                continue
            for node in trace_nodes:
                line = node.get("line")
                if not isinstance(line, int):
                    continue
                depth = node.get("depth", 0)
                parents_payload = node.get("parents", [])
                parents: list[tuple[str, int]] = []
                if isinstance(parents_payload, list):
                    for parent in parents_payload:
                        if isinstance(parent, dict):
                            parent_type = str(parent.get("parent_node_type", ""))
                            parent_line = parent.get("parent_node_line")
                            if isinstance(parent_line, int):
                                parents.append((parent_type, parent_line))
                nodes.append(
                    CounterExampleNode(
                        line=line,
                        depth=int(depth) if isinstance(depth, int) else 0,
                        type=str(node.get("type", "")),
                        source=str(node.get("source", "")),
                        content=str(node.get("content", "")),
                        trace_id=int(trace_id) if isinstance(trace_id, int) else 0,
                        parents=parents,
                    )
                )
        return nodes

    def get_fault_localization(self, file: Path) -> list[int]:
        # Reassume is heavier than CounterExampleIf on some mutants.
        # Give it a technique-specific timeout floor to avoid false empty predictions.
        reassume_max_time = 2*gl.MAX_TIME_EXTERNAL_PROGRAMS

        # Create command to run 
        base_dir = gl.BASE_PATH / "build_output/CounterExampleIfReassume"
        pattern = "**/CounterExampleIfReassume"
        executable = _find_executable(base_dir, pattern)
               # run this command and get the output on a variable
        command: list[str] = [
            str(executable),
            str(file),
            "--max-time", str(reassume_max_time),
            "--max-ram", str(gl.MAX_RAM_EXTERNAL_PROGRAMS)
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

        try:
            parsed_nodes = self._parse_output(stdout)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse CounterExampleIfReassume output for file {file}: {e}")
            return []

        nodes: list[CounterExampleNode] = []
        # Collect all lines from all counter-examples and track frequency/depth
        for node in parsed_nodes:
            nodes.append(node)

        if len(nodes) == 0:
            return []
        
        
        return self._rank_lines(nodes)
