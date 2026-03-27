// dafny 4.11.1.0
// 
// example_to_test.dfy

method abs1(x: int) returns (y: int)
  ensures x > 0 ==> y == x
  ensures x<  0 ==> y == x + 1
  decreases x
{
  if x > 1 {
    y := x + 1;
    return y;
  }
  if x > 0 {
    y := x + 2;
    return y;
  }
  if x < -1 {
    y := x + 2;
    return y;
  }
  if x < 0 {
    y := x + 3;
    return y;
  }
  return x;
}
