// dafny 4.11.1.0
// 
// example_to_test.dfy

method abs1(x: int) returns (y: int)
  ensures x > 0 ==> y == x
  decreases x
{
  if x > 3 {
    y := x + 1;
    return y;
  }
  if x > 1 {
    y := x + 1;
    return x + 1;
  }
  return x;
}
// ---- Suspicious nodes detected ----
// Suspicious node at line 15
// Suspicious node at line 16
// Suspicious node at line 17
