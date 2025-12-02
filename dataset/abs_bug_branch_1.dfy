method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
{
    if(x > 0){
        y := x + 1; // Position Does not appear on Default Dafny
    } else {
        y := -x;
    }
}