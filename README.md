# This Repo Explores diverse ideas to find fault localization in dafny programns 

# Generate the dataset to evaluate the mutants and the FL methods
 ./src/generate\_mutdafny\_datset.sh 




After running mutdafny and some dataset and generating the mutants and the original dir. 
get\_pos computes the diff from the original program. 

change to src directory and run:
./get\_pos.sh

It generates a folder pos\_mutation with:
original/{names}.dfy containing all programs original (after post resolution) 
killed/{names}\_\_{infos}.dfy with the mutant
killed/{names}\_\_{infos}.txt with the diff between original program and mutant

# Possibilities 

##  Build in Dafny
The Dafny verifier already produces a basic identification of the failure positions. Internally, it adds assertions of postconditions on all function returns, which in some cases allows identifying where the failure occurs.

That said, if the failure does not occur in a return statement, this method is not effectiv#e

## Use Counterexamples to identify failure Positions 
It is possible to generate counterexamples to locate the failure in a branch. Once a counterexample is generated, the affected positions in the source code can be identified.

Limitations: Only one counterexample is generated per program. If there are multiple failure points, the others may not be detected after generating the first counterexample.

## Use Isolate Assertions with isolate\_paths 
Not needed in the sense that the counteexamples generated one by one is able to retrieve the path (and seems a better aprroach for now)



By passing the --isolate-assertions flag to the verifier and using isolate\_paths as a plugin, all paths and assertions are verified separately. This allows pinpointing exactly which paths caused failures and provides a complete list of all failing paths and assertions.

Explanation from Dafny documentation:

You can instruct Dafny to verify individual assertions in separate batches.

The {:isolate} attribute can be placed on a single assertion to isolate it, or on a symbol (like a function or method) with {:isolate\_assertions} to isolate all assertions in that symbol.

The CLI option --isolate-assertions isolates all assertions in all symbols.

{:isolate} can be used on assert, return, and continue statements. Placed on a return, it verifies postconditions for all paths leading to that return in a separate batch. Placed on a continue, it verifies loop invariants for all paths leading to that continue.

Furthermore, each control flow path leading to an isolated assertion can also be placed in a separate batch using {:isolate "paths"}.

This approach could allow generating counterexamples for all failing paths.

## Extend Previous Work
Reference: Specification-Guided Repair of Arithmetic Errors in Dafny Programs using LLMs
https://arxiv.org/pdf/2507.03659

It’s unclear how generic this approach would be or how easily it could be adapted to other transformations, as it relies on weakest precondition (WP) calculation, which bypasses Dafny’s framework.


# Recommended Approach 
Option 3 seems the most practical and least reinventive. It integrates well with the current verifier.

A potential implementation could be a Dafny plugin that, after resolution, adds {:isolate "paths"} to the relevant paths. Using this approach, it might also be possible to generate counterexamples for all failing paths.

It seems that option 3 is not needed:

1) We can extend counterexmaple generations to achieve complete counterexample creation.
2) From the complete list of countexamples traces we can metric the most promising lines where the deffects are

3) We can also use Coverage metrics as a heuristic: If a line is used in a assertion prove maybe it is correct only ones that are not maybe are incorrect (and this can possible speed up things)


# If wanted to generate tests we could create a took that from the couterexamples creates runnable tests.

But really with this i do not see the usecase for generating tests


# TODOS 
- Make Dataset small to test ideas 



