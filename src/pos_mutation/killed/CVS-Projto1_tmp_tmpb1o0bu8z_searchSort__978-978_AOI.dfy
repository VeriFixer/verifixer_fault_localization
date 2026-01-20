// CVS-Projto1_tmp_tmpb1o0bu8z_searchSort.dfy

method fillK(a: array<int>, n: int, k: int, c: int)
    returns (b: bool)
  requires 0 <= c <= n
  requires n == a.Length
  decreases a, n, k, c
{
  if c == 0 {
    return true;
  }
  var p := 0;
  while p < c
    invariant 0 <= p <= c
    decreases c - p
  {
    if a[p] != k {
      return false;
    }
    p := p + 1;
  }
  return true;
}

method containsSubString(a: array<char>, b: array<char>) returns (pos: int)
  requires 0 <= b.Length <= a.Length
  decreases a, b
{
  pos := -1;
  if b.Length == 0 {
    return pos;
  }
  var p := 0;
  while p < a.Length
    invariant 0 <= p <= a.Length
    decreases a.Length - p
  {
    if a.Length - p < b.Length {
      return pos;
    }
    if a[p] == b[0] {
      var i := 0;
      while i < b.Length
        decreases b.Length - i
      {
        if a[i + p] != b[i] {
          return -1;
        }
        i := i + -1;
      }
      pos := p;
      return pos;
    }
    p := p + 1;
  }
}
