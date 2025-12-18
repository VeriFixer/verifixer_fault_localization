from pathlib import Path
import random
from fl_eval.core.abstract import FLTechnique # Import ABC

class RandomRanker(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_fault_localization(self, file: Path) -> list[int]:
        with open(file, "r") as f:
            lines = f.readlines()

        line_numbers = list(range(1, len(lines) + 1))
        random.shuffle(line_numbers)
        return line_numbers

import os
import subprocess
import json
import re

class CounterExampleBaseRanker(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_counterexample_lines_from_json_diagnostic(self, diagnostic : dict[Any]) -> tuple[bool, list[int]]:
        lines_on_counterexamples : list[int] = []
        try:
            counter_message: str = diagnostic["value"]["defaultFormatMessage"]
        except KeyError:
            # Handle cases where the dictionary structure is unexpected
            return (False, lines_on_counterexamples)

        counter_message = diagnostic["value"]["defaultFormatMessage"]
        counterexample_must_have_string = "DafnyRef#sec-counterexamples"
        was_found_counter_example = False
        line_column_pattern = re.compile(r"\((\d+),\s*\d+\)")
        lines_on_counterexamples = []
        for line in counter_message.split("\n"):
            if(counterexample_must_have_string in line):
                was_found_counter_example = True
            if(was_found_counter_example):
               matches = line_column_pattern.findall(line)
               if matches:
                    for line_str in matches:
                        line_number = int(line_str)
                        lines_on_counterexamples.append(line_number)

        return (was_found_counter_example, lines_on_counterexamples)

    def get_fault_localization(self, file: Path) -> list[int]:
        DAFNY_EXEC = os.environ.get("DAFNY_EXEC")
        assert (DAFNY_EXEC != None), "an environmental variable DAFNY_EXEC must be set to dafny binary path"
        assert(file.exists()), "File should exist when calling this function"

        # run this command and get the output on a variable
        command = [
            DAFNY_EXEC,
            "verify",
            str(file),
            "--extract-counterexample",
            "--json-output"
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False  # Don't raise exception for non-zero exit codes yet
        )

        # Separate json in actuall newlines need to escape new lines \\n inside json and put them back together
        placeholder = "___ESCAPED_NEWLINE_PLACEHOLDER___"
        result_changed_stdout = result.stdout.replace("\\n",placeholder)
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
    

#file = "/home/ricostynha/Desktop/verifixer_fault_localization/abs__-_ODL_Add-left.dfy"
#ct = CounterExampleBaseRanker("counter1")
#ct.get_fault_localization(Path(file))