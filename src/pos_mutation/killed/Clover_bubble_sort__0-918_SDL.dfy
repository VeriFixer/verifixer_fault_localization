// Clover_bubble_sort.dfy

method BubbleSort(a: array<int>)
  modifies a
  ensures forall i: int, j: int {:trigger a[j], a[i]} :: 0 <= i < j < a.Length ==> a[i] <= a[j]
  ensures multiset(a[..]) == multiset(old(a[..]))
  decreases a
{
}
