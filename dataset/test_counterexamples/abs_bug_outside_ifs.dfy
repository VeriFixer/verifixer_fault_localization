method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
{
    if(x > 0){
        y := x;
    } else {
        y := -x;
    }
    y := y + 1; // Position cannot be pin pointed by counterexamples all lines appear to be contributing
                // What is expected, but maybe we can make better
}

// abs_bug_outside_ifs.dfy(4,0): Error: a postcondition could not be proved on this return path
//  Related counterexample:
//  WARNING: the following counterexample may be inconsistent or invalid. See dafny.org/dafny/DafnyRef/DafnyRef#sec-counterexamples
//  abs_bug_outside_ifs.dfy(4,0): initial state:
//  assume 1 == x;
//  abs_bug_outside_ifs.dfy(6,14):
//  assume 1 == x && 1 == y;
//  abs_bug_outside_ifs.dfy(10,14):
//  assume 1 == x && 2 == y;
 
//   |
// 4 | {
//   | ^

// abs_bug_outside_ifs.dfy(2,26): Related location: this is the postcondition that could not be proved
//   |
// 2 |     ensures (x > 0) ==> y == x
//   |                           ^^

// abs_bug_outside_ifs.dfy(4,0): Error: a postcondition could not be proved on this return path
//  Related counterexample:
//  WARNING: the following counterexample may be inconsistent or invalid. See dafny.org/dafny/DafnyRef/DafnyRef#sec-counterexamples
//  abs_bug_outside_ifs.dfy(4,0): initial state:
//  assume 0 == x;
//  abs_bug_outside_ifs.dfy(8,15):
//  assume 0 == x && 0 == y;
//  abs_bug_outside_ifs.dfy(10,14):
//  assume 0 == x && 1 == y;
 
//   |
// 4 | {
//   | ^

// abs_bug_outside_ifs.dfy(3,27): Related location: this is the postcondition that could not be proved
//   |
// 3 |     ensures (x <= 0) ==> y == -x
//   |                            ^^

