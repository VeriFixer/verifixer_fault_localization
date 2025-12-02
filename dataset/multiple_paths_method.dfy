method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
{
    if(x > 0){
        y := x;
        if(x>4){
            y := x + 1;
        } else {
            y := x;
        }
    } else {
       y := -x;
        if(x <4){
            y := x;
        } else {
            y := x;
        }
    }
}