// Clover_bubble_sort.dfy

method BubbleSort(a: array<int>)
  modifies a
  ensures forall i: int, j: int {:trigger a[j], a[i]} :: 0 <= i < j < a.Length ==> a[i] <= a[j]
  ensures multiset(a[..]) == multiset(old(a[..]))
  decreases a
{
  var i := a.Length - 1;
  while i > 1
    invariant i < 0 ==> a.Length == 0
    invariant -1 <= i < a.Length
    invariant forall ii: int, jj: int {:trigger a[jj], a[ii]} :: i <= ii < jj < a.Length ==> a[ii] <= a[jj]
    invariant forall k: int, k': int {:trigger a[k'], a[k]} :: 0 <= k <= i < k' < a.Length ==> a[k] <= a[k']
    invariant multiset(a[..]) == multiset(old(a[..]))
    decreases i - 1
  {
    var j := 0;
    while j < i
      invariant 0 < i < a.Length && 0 <= j <= i
      invariant forall ii: int, jj: int {:trigger a[jj], a[ii]} :: i <= ii <= jj < a.Length ==> a[ii] <= a[jj]
      invariant forall k: int, k': int {:trigger a[k'], a[k]} :: 0 <= k <= i < k' < a.Length ==> a[k] <= a[k']
      invariant forall k: int {:trigger a[k]} :: 0 <= k <= j ==> a[k] <= a[j]
      invariant multiset(a[..]) == multiset(old(a[..]))
      decreases i - j
    {
      if a[j] > a[j + 1] {
        a[j], a[j + 1] := a[j + 1], a[j];
      }
      j := j + 1;
    }
    i := i - 1;
  }
}
