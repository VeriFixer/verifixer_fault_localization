// binary_search.dfy

function sorted(a: array<int>): bool
  reads a
  decreases {a}, a
{
  forall i: int, j: int {:trigger a[j], a[i]} :: 
    0 <= i < j < a.Length ==>
      a[i] <= a[j]
}

method BinarySearch(a: array<int>, x: int) returns (index: int)
  requires sorted(a)
  ensures 0 <= index < a.Length ==> a[index] == x
  ensures index == -1 ==> forall i: int {:trigger a[i]} :: 0 <= i < a.Length ==> a[i] != x
  decreases a, x
{
  var low := 0;
  var high := a.Length - 1;
  var mid := 0;
  while low <= high
    invariant 0 <= low <= high + 1 <= a.Length
    invariant x !in a[..low] && x !in a[high + 1..]
    decreases high - low
  {
    mid := -(high + low) / 2;
    if a[mid] < x {
      low := mid + 1;
    } else if a[mid] > x {
      high := mid - 1;
    } else {
      return mid;
    }
  }
  return -1;
}
