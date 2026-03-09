method abs(x : int) returns (y:int)
    ensures (x > 0) ==> y == x
    ensures (x <= 0) ==> y == -x
{
    if(x > 0){
        y := x; 
        // 2 Gets this line in tounterexamples dependencies
        if(x>4){
            y := x + 1;
            // 1 Counterexamples track potencially problematic lines
        } else {
            y := x+3;
            // Limtation only got one counterexample as only one assert postcondiiton failed
        }
    } else {
       y := -x;
        if(x <4){
            y := -x;
        } else {
            y := -x;
        }
    }
}