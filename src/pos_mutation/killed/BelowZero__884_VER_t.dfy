// BelowZero.dfy

function sum(s: seq<int>, n: nat): int
  requires n <= |s|
  decreases s, n
{
  if |s| == 0 || n == 0 then
    0
  else
    s[0] + sum(s[1..], n - 1)
}

lemma sum_plus(s: seq<int>, i: nat)
  requires i < |s|
  ensures sum(s, i) + s[i] == sum(s, i + 1)
  decreases s, i
{
}

method BelowZero(ops: seq<int>) returns (result: bool)
  ensures result <==> exists n: nat {:trigger sum(ops, n)} :: n <= |ops| && sum(ops, n) < 0
  decreases ops
{
  result := false;
  var t := 0;
  for i: int := 0 to |ops|
    invariant t == sum(ops, i)
    invariant forall n: nat {:trigger sum(ops, n)} :: n <= i ==> sum(ops, n) >= 0
  {
    t := t + ops[i];
    sum_plus(ops, t);
    if t < 0 {
      result := true;
      return;
    }
  }
}
