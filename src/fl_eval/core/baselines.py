from pathlib import Path
import random
from fl_eval.core.abstract import FLTechnique # Import ABC
import os
import subprocess
import json
import re

import fl_eval.util.run_external_cmd as run_cmd

# Empty ranker in the score function is equivalent to 
# chosing on average the correct line in half the entries
# As the score function for the non selected lines returns the expected
# lines to test from the non tested lines for completness
class EmptyRanker(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_fault_localization(self, file: Path) -> list[int]:
        line_numbers: list[int] = []
        return line_numbers
    
class RandomRanker(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_fault_localization(self, file: Path) -> list[int]:
        with open(file, "r") as f:
            lines = f.readlines()
        line_numbers = list(range(1, len(lines) + 1))
        random.shuffle(line_numbers)
        return line_numbers

import fl_eval.util.globals as gl
class RandomLineOfMethodThatFails(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)

    def get_fault_localization(self, file: Path) -> list[int]:
        # Create command to run 
        exec = gl.BASE_PATH / "strategies/ReturnAtRandomAllLinesOfFailingMethod/bin/Debug/net8.0/ReturnAtRandomAllLinesOfFailingMethod"
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


class CounterExampleBaseRanker(FLTechnique):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.dafny = os.environ.get("DAFNY_EXEC") or ""
        assert (self.dafny != None), "an environmental variable DAFNY_EXEC must be set to dafny binary path"

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
        assert(file.exists()), "File should exist when calling this function"

        # run this command and get the output on a variable
        command: list[str] = [
            self.dafny,
            "verify",
            str(file),
            "--extract-counterexample",
            "--json-output"
        ]

        (status, stdout, _) = run_cmd.run_external_cmd(command)
        if(status != run_cmd.Status.OK):
            # If run cmd finished by any reason with error send empty prediction
            return []
        
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
    

#file = "/home/ricostynha/Desktop/verifixer_fault_localization/abs__-_ODL_Add-left.dfy"
#ct = CounterExampleBaseRanker("counter1")
#print(ct.get_fault_localization(Path(file)))