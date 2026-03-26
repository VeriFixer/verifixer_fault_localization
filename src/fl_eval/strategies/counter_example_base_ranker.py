from fl_eval.core.abstract import FLTechnique
import fl_eval.util.run_external_cmd as run_cmd
import config as gl
from typing import Any
from pathlib import Path
import json
import re
import os

class CounterExampleBaseRanker(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.dafny = os.environ.get("DAFNY_EXEC") or "dafny"
        if self.dafny is None:
            raise ValueError("DAFNY_EXEC environment variable must be set or dafny must be in PATH")

    def get_counterexample_lines_from_json_diagnostic(self, diagnostic: dict[str, Any]) -> tuple[bool, list[int]]:
        lines_on_counterexamples : list[int] = []
        try:
            counter_message: str = diagnostic["value"]["defaultFormatMessage"]
        except KeyError:
            # Handle cases where the dictionary structure is unexpected
            return (False, lines_on_counterexamples)

        counter_message = diagnostic["value"]["defaultFormatMessage"]
        counterexample_must_have_string = "DafnyRef#sec-counterexamples"
        was_found_counter_example = False
        line_column_pattern = re.compile(r"dfy\((\d+),\s*\d+\)")
        lines_on_counterexamples = []
        for line in counter_message.split("\n"):
            if(counterexample_must_have_string in line):
                was_found_counter_example = True
            if(was_found_counter_example):
               if("Related location" in line): # Related location point to postcondition
                   continue
               matches = line_column_pattern.findall(line)
               if matches:
                    for line_str in matches:
                        line_number = int(line_str)
                        lines_on_counterexamples.append(line_number)

        return (was_found_counter_example, lines_on_counterexamples)

    def get_fault_localization(self, file: Path) -> list[int]:
        if not file.exists():
            raise FileNotFoundError(f"File does not exist: {file}")

        # run this command and get the output on a variable
        command: list[str] = [
            self.dafny,
            "verify",
            str(file),
            "--allow-warnings",
            "--extract-counterexample",
            "--json-output",
            "--verification-time-limit", str(gl.MAX_TIME_EXTERNAL_PROGRAMS),
            f"--solver-option:O:memory_max_size={gl.MAX_RAM_EXTERNAL_PROGRAMS*1000}"

        ]

        (status, stdout, stderr) = run_cmd.run_external_cmd(command)
        
        # Separate json in actuall newlines need to escape new lines \\n inside json and put them back together
        placeholder = "___ESCAPED_NEWLINE_PLACEHOLDER___"
        result_changed_stdout = stdout.replace("\\n",placeholder)
        results_json_list: list[str] = result_changed_stdout.split("\n")
        results_json_list = list(filter(lambda x: len(x) > 0, results_json_list))
        results_json_list = [r.replace(placeholder,"\\n") for r in results_json_list]


        diagnostics = []
        for result in results_json_list:
            result_json = json.loads(result)
            if(result_json["type"] == "diagnostic"):
                diagnostics.append(result_json)
        
        # Will use basic Grouping (meaning all lines are gatherer per order)
        # But better strategies as pairing the indeixes on the returned lines considering the botton ones can be better 
        all_lines: list[int] = []
        for diagnostic in diagnostics:
            (iscounter, lines_counter) = self.get_counterexample_lines_from_json_diagnostic(diagnostic)
            if(iscounter):
                all_lines += lines_counter

        # Remove duplicates 
        all_lines_no_dup: list[int] = []
        for line in all_lines:
            if(line not in all_lines_no_dup):
                all_lines_no_dup.append(line)
        
        return all_lines_no_dup