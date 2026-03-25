# Strategy ReturnAtRandomAllLinesOfFailingMethod

Used verifier to find start and end lines of failing method and returns all liner per order indicated. 


# Counterexample base
dafny verify --extract-counterexample abs__121-127_COI.dfy 

```dafny
// abs.dfy

method absplus1(x: int) returns (y: int)
  ensures x > 0 ==> y == x + 1
  ensures x <= 0 ==> y == -x + 1
  decreases x
{




  if !(x > 0) {
    var a := 3;
    y := x + 1;
    var b := 3;
    var c := 3;
  } else {
    y := -x + 1;
  }
}
```

It returns:
```txt
abs__121-127_COI.dfy(7,0): Error: a postcondition could not be proved on this return path
 Related counterexample:
 WARNING: the following counterexample may be inconsistent or invalid. See dafny.org/dafny/DafnyRef/DafnyRef#sec-counterexamples
 abs__121-127_COI.dfy(7,0): initial state:
 assume 1 == x;
 abs__121-127_COI.dfy(18,15):
 assume 1 == x && 0 == y;
 
  |
7 | {
  | ^

abs__121-127_COI.dfy(4,22): Related location: this is the postcondition that could not be proved
  |
4 |   ensures x > 0 ==> y == x + 1
  |                       ^^

abs__121-127_COI.dfy(7,0): Error: a postcondition could not be proved on this return path
 Related counterexample:
 WARNING: the following counterexample may be inconsistent or invalid. See dafny.org/dafny/DafnyRef/DafnyRef#sec-counterexamples
 abs__121-127_COI.dfy(7,0): initial state:
 assume -1 == x;
 abs__121-127_COI.dfy(13,14):
 assume -1 == x && 3 == a;
 abs__121-127_COI.dfy(14,14):
 assume -1 == x && 0 == y && 3 == a;
 abs__121-127_COI.dfy(15,14):
 assume -1 == x && 0 == y && 3 == a && 3 == b;
 abs__121-127_COI.dfy(16,14):
 assume -1 == x && 0 == y && 3 == a && 3 == b && 3 == c;
 
  |
7 | {
  | ^

abs__121-127_COI.dfy(5,23): Related location: this is the postcondition that could not be proved
  |
5 |   ensures x <= 0 ==> y == -x + 1
  |                        ^^

```

Notes: Identifies the Code block
Limitations 
1. it does not identify at all the if(the decision points), here the problem is the decision point
2. inside the block it cannot find unrelated lines of code it returns all lines 

This example would be easily catched if the if points were tracked in both counterexamples. 
augmenting to 1.
 abs__121-127_COI.dfy(7,0): initial state:
 assume 1 == x;
 abs__121-127_COI.dfy(12,0):
 abs__121-127_COI.dfy(18,15):
 assume 1 == x && 0 == y;

 And if we ignore the inital state the only line repeated is that line, so it is the one that has the error

# Counterexample Returning complete counterexample with decision lines (ifs)

After a counterexample the postcondition that fails in the first counterexaxmple is simply assumed on top.

The best to achieve the best: is for only that branch to be assumed that postcondition ! (Example)

method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    //ensures (x <= 0) ==> y == -x
{
    if(x > 3){
        y := x + 1; // Verification trace gets localization precisely
        assume (x > 0) ==> y == x; // Added assume postcondition when fails in that branch manages to catch more counterexamples
        return y;
    } 

    if(x > 1){
        return x + 1; // Line captured with the modification !!!! 
    }
    
   
    return x;
}

// Thats the problem the counterexample only generate 1 counteexample for each postcondiiton
// What I can is if fails assume the postcondition on the failing branch before return 
// And rerun it

# Limitations of counterexample untill now 

datasets/dafnytestgen_tests_can_run/killed/formal_verication_dafny_tmp_tmpwgl2qz28_Challenges_ex2__867_BBR_true.dfy

tracing ignores the first line 

if the error is on the first line of like an if 
if(cenas){
  error
}

the error line is not traced on the counterexample! (this is a issue to address)

2) This seems really a problem on the conterexample itself 

  /app/datasets/dafnytestgen_tests_can_run/killed/dafleet_tmp_tmpa2e4kb9v_0001-0050_0005-longest-palindromic-substring__1733_COR_Imp.dfy

  (But botht these were not related to ensures so maybe thats the catch)

3) This will just not work 
/app/datasets/dafnytestgen_tests_can_run/killed/dafleet_tmp_tmpa2e4kb9v_0001-0050_0005-longest-palindromic-substring__6949_SAR_6961.dfy


Ok will change strategy: If no line es flagge will not send a default line at the beginning on the counterexample (probably that is jeopardizing my changes.)

And will classify also not the full file but on the method probably is better