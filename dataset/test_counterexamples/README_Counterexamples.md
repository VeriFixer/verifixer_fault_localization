# This will detail the command to run the counterexamples

It seems that up two two counterexamples are displayed in the dafny editor

# By cli extract only one counterexample it seems
ricostynha@nobara-pc:~/Desktop/verifixer_fault_localization/dataset/test_counterexamples$ dafny verify --extract-counterexample abs_bug_branch_1.dfy 
abs_bug_branch_1.dfy(4,0): Error: a postcondition could not be proved on this return path
 Related counterexample:
 WARNING: the following counterexample may be inconsistent or invalid. See dafny.org/dafny/DafnyRef/DafnyRef#sec-counterexamples
 abs_bug_branch_1.dfy(4,0): initial state:
 assume 1 == x;
 abs_bug_branch_1.dfy(6,18):
 assume 1 == x && 2 == y;
 
  |
4 | {
  | ^

abs_bug_branch_1.dfy(2,26): Related location: this is the postcondition that could not be proved
  |
2 |     ensures (x > 0) ==> y == x
  |                           ^^


Dafny program verifier finished with 0 verified, 1 error
# It can extract many counterexamples if they are related to makeing fail different postconditions

If they made fail the same asertion/postcondiiton so only the first one is generated

# One improvement we can make is: 
After finding a counterexample assume the failing assertions in the end of the counterexample block and then rerun to catch more if any.

(it is is fact somehing simmilar for what is already done for managing multiple to find counterxamples for unrelated assertions. But allowing to pinpoint all paths with problems).

# Idea When generating all counterxamples we can se lines that appear in multiple that porbably indicate lines with higher proability of having the error
dataset/test_counterexamples/abs_bug_outside_ifs.dfy

the failing line appears in two counterexamples, instead of one for the others, highlingting that potencially the biggest error is there. 

Possibly we could generate tests here: 
 - The ones on dafny are create now to achieve complete code coverage
 - How can this be extended to achieve complete specificaiton coverage? 

Specification Coverage we have defines as:
 - specifications used on proof lines that needed code something simmilar with that. But doing so it is necessary for the proof to be complete so for now no. 

 Bit obseving the following specification:
 ```dafny
 method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
```
This specification can be targetted by two tests one x > 0 and other x <= 0
for this case it is simple but for the cases

 ```dafny
 method sort(v : int[]) returns (y:int[])
    ensures forall i,j :: 0<i<j<len(y) y[i] < y[j]
    ensures multiset(x) == multiset(y)
    ensures len(v) == len(y)
```
a specificaiton like this would be checked, by ? no idea the tests

# Can we also use a property base testing engine to generate tests? 


# On dafny documentation
If the verifier returns a counterexample, this counterexample is used to determine both the failing assertion and the failing path. In order to retrieve additional failing assertions, dafny will again query the verifier after turning previously failed assertions into assumptions.23 24

--extract-counterexample - if verification fails, report a potential counterexample as a set of assumptions that can be inserted into the code. Note that Danfy cannot guarantee that the counterexample it reports provably violates the assertion or that the assumptions are not mutually inconsistent (see 17), so this output should be inspected manually and treated as a hint.

The formula sent to the underlying SMT solver is the negation of the formula that the verifier wants to prove - also called a VC or verification condition. Hence, if the SMT solver returns “unsat”, it means that the SMT formula is always false, meaning the verifier’s formula is always true. On the other side, if the SMT solver returns “sat”, it means that the SMT formula can be made true with a special variable assignment, which means that the verifier’s formula is false under that same variable assignment, meaning it’s a counter-example for the verifier. In practice and because of quantifiers, the SMT solver will usually return “unknown” instead of “sat”, but will still provide a variable assignment that it couldn’t prove that it does not make the formula true. dafny reports it as a “counter-example” but it might not be a real counter-example, only provide hints about what dafny knows