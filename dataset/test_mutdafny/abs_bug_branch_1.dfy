method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
{
    if(x > 0){
        y := x + 1; // Verificaiton trace gets localization precisely
    } else {
        y := -x;
    }
}

// With Cli 
// dafny verify --extract-counterexample abs_bug_branch_1.dfy 
// abs_bug_branch_1.dfy(4,0): Error: a postcondition could not be proved on this return path
//  Related counterexample:
//  WARNING: the following counterexample may be inconsistent or invalid. See dafny.org/dafny/DafnyRef/DafnyRef#sec-counterexamples
//  abs_bug_branch_1.dfy(4,0): initial state:
//  assume 1 == x;
//  abs_bug_branch_1.dfy(6,18):
//  assume 1 == x && 2 == y;
 
//   |
// 4 | {
//   | ^

// abs_bug_branch_1.dfy(2,26): Related location: this is the postcondition that could not be proved
//   |
// 2 |     ensures (x > 0) ==> y == x
//   |  