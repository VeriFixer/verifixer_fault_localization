method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
{
    if(x > 0){
        return x+1; // Default Dafny localizes
    } else {
        return -x;
    }
}