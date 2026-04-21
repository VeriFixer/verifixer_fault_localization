from os import listdir, path
from pathlib import Path

mutation_operators_descriptions = {
    "AOR": "Replacement of an arithmetic operator with another",
    "ROR": "Replacement of a relational operator with another",
    "COR": "Replacement of a conditional operator with another",
    "LOR": "Replacement of a logical operator with another",
    "SOR": "Replacement of a shift operator with another",
    "BBR": "Replacement of a relational or conditional expression with \\texttt{true} or \\texttt{false}",
    "AOI": "Insertion of a unary minus in front of an arithmetic expression",
    "COI": "Insertion of a \\texttt{not} operator in front of a conditional expression",
    "LOI": "Insertion of a \\texttt{not} operator in front of a logical expression",
    "AOD": "Deletion of a unary minus in front of an arithmetic expression",
    "COD": "Deletion of a \\texttt{not} operator in front of a conditional expression",
    "LOD": "Deletion of a \\texttt{not} operator in front of a logical expression",
    "LVR": "Replacement of a numerical literal value with its increment, decrement and zero and of a string literal value either an empty one, a default one, or a mutation of the original",
    "EVR": "Replacement of an expression with a default literal value of its type",
    "VER": "Replacement of a variable with another of the same type",
    "LSR": "Replacement of continue with \\texttt{break} and of \\texttt{break} with ether \\texttt{continue} or \\texttt{return}",
    "LBI": "Insertion of a \\texttt{break} statement at the beggining of the body of a loop",
    "MRR": "Replacement of a method call with a default literal of its return type",
    "MAP": "Replacement of a method call with one of its arguments with the same type as the return value",
    "MNR": "Deletion of a class method call, its receiver being mantained",
    "MCR": "Replacement of a method call with another method with the same signature",
    "MVR": "Replacement of a method call with a variable of the same type",
    "SAR": "Swap a method call argument with another used in the same method call with the same type",
    "CIR": "Replacement of non-empty collection initializers with an empty one and of empty initializers with a default non-empty one",
    "CBR": "Replacement of match statement cases with the default one and of the default label with one provided by the programmer",
    "CBE": "Extraction of one of the blocks of an if or if-then-else statement to the outside scope and deletion of the remaining ones",
    "TAR": "Replacement of the index used in a tuple element access",
    "DCR": "Replacement of a datatype constructor with another of the same datatype and with the same signature",
    "FAR": "Replacement of a class's field access with a different field of the same class",
    "SDL": "Deletion of a statement or of an entire code block",
    "VDL": "Deletion of all occurences of a variable",
    "SLD": "Deletion of either the bottom or top limit of a subsequence selection expression",
    "ODL": "Deletion of all occurences of a binary operator (and of one of its arguments in order to preserve program validity)",
    "THI": "Insertion of the \\texttt{this} keyword in front of the use of a parameter that has the same name as a class field",
    "THD": "Deletion of the \\texttt{this} keyword in front of the use of a class field that has the same name as a parameter",
    "AMR": "Replacement of the body of an accessor (get) method with another with the same signature",
    "MMR": "Replacement of the body of a modifier (set) method with another with the same signature",
    "PRV": "Replacement of a child reference assignment to a parent with a child reference of a different type",
    "SWS": "Swap a statement with the one either immediately below or above it",
    "SWV": "Swap the RHS of a variable declaration statement with the one from the variable declaration immediately below or above it"
}
mutation_operators_distribution = {
    "AOR": 0, "ROR": 0, "COR": 0, "LOR": 0, "SOR": 0, "BBR": 0,
    "AOI": 0, "COI": 0, "LOI": 0, "AOD": 0, "COD": 0, "LOD": 0,
    "LVR": 0, "EVR": 0, "VER": 0, "LSR": 0, "LBI": 0, "MRR": 0,
    "MAP": 0, "MNR": 0, "MCR": 0, "MVR": 0, "SAR": 0, "CIR": 0,
    "CBR": 0, "CBE": 0, "TAR": 0, "DCR": 0, "FAR": 0, "SDL": 0,
    "VDL": 0, "SLD": 0, "ODL": 0, "THI": 0, "THD": 0, "AMR": 0,
    "MMR": 0, "PRV": 0, "SWS": 0, "SWV": 0
}

dataset_files="/app/datasets/dafnytestgen_tests_can_run/killed/"
programs = listdir(dataset_files)
for program in programs:
    if not (program.endswith(".dfy") and not program.endswith(".test.dfy")):
        continue
    program = Path(program).stem
    if path.getsize(f"{dataset_files}/{program}.txt") == 0:
        continue

    components = program.split("_")
    operator = set(components).intersection(mutation_operators_distribution.keys()).pop()
    mutation_operators_distribution[operator] += 1


table = """
\\begin{table}[h]
\\centering
\\begin{tabular}{p{0.05\columnwidth}p{0.7\columnwidth}p{0.1\columnwidth}}
\\hline
\\textbf{Op.} & \\textbf{Description} & \\textbf{\\# Mutants} \\\\
\\hline
"""
for mutation_operator in mutation_operators_distribution:
    description = mutation_operators_descriptions[mutation_operator]
    frequency = mutation_operators_distribution[mutation_operator]
    if frequency != 0:
        table += f"{mutation_operator} & {description} & {frequency} \\\\\n"
table += """
\\hline
\\end{tabular}
\\caption{Mutation operators used for the generation of our artificial fault dataset.}
\\label{tab:mutation-operators-dataset-distribution}
\\end{table}
"""
print(table)
        