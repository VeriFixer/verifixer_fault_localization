method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
{
    if(x > 0){
        y := x;
    } else {
        y := -x;
    }
    y := y + 1; // Position does not appear in default Dafny
}