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