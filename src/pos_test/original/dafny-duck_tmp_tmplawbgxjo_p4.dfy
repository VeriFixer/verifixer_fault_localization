// dafny-duck_tmp_tmplawbgxjo_p4.dfy

method single(x: array<int>, y: array<int>) returns (b: array<int>)
  requires x.Length > 0
  requires y.Length > 0
  ensures b[..] == x[..] + y[..]
  decreases x, y
{
  b := new int[x.Length + y.Length];
  var i := 0;
  var index := 0;
  var sumi := x.Length + y.Length;
  while i < x.Length && index < sumi
    invariant 0 <= i <= x.Length
    invariant 0 <= index <= sumi
    invariant b[..index] == x[..i]
    decreases x.Length - i, if i < x.Length then sumi - index else 0 - 1
  {
    b[index] := x[i];
    i := i + 1;
    index := index + 1;
  }
  i := 0;
  while i < y.Length && index < sumi
    invariant 0 <= i <= y.Length
    invariant 0 <= index <= sumi
    invariant b[..index] == x[..] + y[..i]
    decreases y.Length - i, if i < y.Length then sumi - index else 0 - 1
  {
    b[index] := y[i];
    i := i + 1;
    index := index + 1;
  }
}

method Main()
{
  var a := new int[4] [1, 5, 2, 3];
  var b := new int[3] [4, 3, 5];
  var c := new int[7];
  c := single(a, b);
  assert c[..] == [1, 5, 2, 3, 4, 3, 5];
}
