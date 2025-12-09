method absplus1(x : int) returns (y:int)
    ensures (x > 0) ==> y == x + 1
    ensures (x <= 0) ==> y == -x + 1
{
    if(x > 0){
        y := x + 1;
    } else {
        y := -x + 1;
    }
}
