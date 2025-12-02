method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
{
    if(x > 0){
        y := x;
    } else {
        y := -x + 1; // Verification trace gets position precisely
    }
}
//  dafny verify --extract-counterexample abs_bug_branch_2.dfy 
// abs_bug_branch_2.dfy(4,0): Error: a postcondition could not be proved on this return path
//  Related counterexample:
//  WARNING: the following counterexample may be inconsistent or invalid. See dafny.org/dafny/DafnyRef/DafnyRef#sec-counterexamples
//  abs_bug_branch_2.dfy(4,0): initial state:
//  assume 0 == x;
//  abs_bug_branch_2.dfy(8,19):
//  assume 0 == x && 1 == y;
 
//   |
// 4 | {
//   | ^

// abs_bug_branch_2.dfy(3,27): Related location: this is the postcondition that could not be proved
//   |
// 3 |     ensures (x <= 0) ==> y == -x
//   |                            ^^


// Dafny program verifier finished with 0 verified, 1 error