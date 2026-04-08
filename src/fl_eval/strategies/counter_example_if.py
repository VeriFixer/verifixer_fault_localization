from fl_eval.core.abstract import FLTechnique
import fl_eval.util.run_external_cmd as run_cmd
import config as gl
import json

from dataclasses import dataclass, field

from typing import cast
import re
from pathlib import Path
from fl_eval.util.ranking_strategy import (
    CounterExampleNode,
    RankingStrategy,
    RANK_BY_FREQUENCY,
    SUPPORTED_RANKING_STRATEGIES,
)

# This will try to find globs like this base_dir/**pattern see other files for more examples
def _find_executable(base_dir : Path, pattern : str) -> Path:
        for path in base_dir.rglob(pattern):
            if path.is_file() and "ref" not in path.parts:
                return path
                    
        raise FileNotFoundError(f"Could not find {pattern} executable in {base_dir}")


@dataclass
class LineFrequencyDepth:
    frequency: int = 0
    depths: list[int] = field(default_factory=lambda: cast(list[int], []))
    types: list[str] = field(default_factory=lambda: cast(list[str], []))


class CounterExampleIf(FLTechnique):
    def __init__(
        self,
        name: str,
        ranking_strategy: RankingStrategy = RANK_BY_FREQUENCY,
        **kwargs,
    ) -> None:
        super().__init__(name, **kwargs)
        self.ranking_strategy = ranking_strategy

    def _rank_lines(
        self,
        nodes: list[CounterExampleNode],
    ) -> list[int]:
        """Rank lines by frequency, then depth, then control-statement presence."""
        if self.ranking_strategy not in SUPPORTED_RANKING_STRATEGIES:
            raise ValueError(
                f"Unknown ranking strategy '{self.ranking_strategy}'. "
                f"Supported: {[s.name for s in SUPPORTED_RANKING_STRATEGIES]}"
            )

        # Get nodes frequency and collected depths per line.
        line_freq_depth_map: dict[int, LineFrequencyDepth] = {}
        first_seen_order: dict[int, int] = {}

        for idx, node in enumerate(nodes):
            if node.line not in first_seen_order:
                first_seen_order[node.line] = idx

            if node.line in line_freq_depth_map:
                line_freq_depth_map[node.line].frequency += 1
                line_freq_depth_map[node.line].depths.append(node.depth)
                line_freq_depth_map[node.line].types.append(node.type)
            else:
                line_freq_depth_map[node.line] = LineFrequencyDepth(
                    frequency=1,
                    depths=[node.depth],
                    types=[node.type],
                )

        def has_control_statement_type(types: list[str]) -> bool:
            for t in types:
                if t in ("IfStmt", "WhileStmt"):
                    return True
            return False

        ranked_lines = sorted(
            line_freq_depth_map.keys(),
            key=lambda line: (
                -line_freq_depth_map[line].frequency,
                -max(line_freq_depth_map[line].depths),
                -int(has_control_statement_type(line_freq_depth_map[line].types)),
                first_seen_order[line],
            ),
        )

        return ranked_lines

    @staticmethod
    def _parse_output(stdout: str) -> list[CounterExampleNode]:
        match = re.search(r"JSON_OUTPUT_START\s*(.*?)\s*JSON_OUTPUT_END", stdout, re.S)
        if not match:
            raise ValueError("CounterExampleIf output missing JSON_OUTPUT_START/JSON_OUTPUT_END markers")

        payload = json.loads(match.group(1))
        traces = payload.get("traces")
        if not isinstance(traces, list):
            raise ValueError("CounterExampleIf output missing 'traces' array")

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
        # Create command to run 
        base_dir = gl.BASE_PATH / "build_output/CounterExampleIf"
        pattern = "**/CounterExampleIf"
        exec = _find_executable(base_dir, pattern)
               # run this command and get the output on a variable
        command : list[str] = [
            str(exec),
            str(file),
            "--max-time", str(gl.MAX_TIME_EXTERNAL_PROGRAMS),
            "--max-ram", str(gl.MAX_RAM_EXTERNAL_PROGRAMS)
        ]

        (status, stdout, stderr) = run_cmd.run_external_cmd(command)
        try:
            parsed_nodes = self._parse_output(stdout)
        except Exception as e:
                # If run cmd finished by any reason with error send empty prediction
            print(
                f"Command crashed\n"
                f"Command : {" ".join(command)}\n"
                f"Status  : {status}\n"
                f"Stdout  : {stdout}\n"
                f"Stderr  : {stderr}\n"
                "---------------------"
                )


            print(f"Failed to parse CounterExampleIfReassume output for file {file}: {e}")
            return []

        nodes: list[CounterExampleNode] = []
        # Collect all lines from all counter-examples and track frequency/depth
        for node in parsed_nodes:
            nodes.append(node)

        if len(nodes) == 0:
            return []
        
        
        return self._rank_lines(nodes)

