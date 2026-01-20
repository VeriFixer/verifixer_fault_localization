// dafleet_tmp_tmpa2e4kb9v_0001-0050_0005-longest-palindromic-substring.dfy

ghost predicate palindromic(s: string, i: int, j: int)
  requires 0 <= i <= j <= |s|
  decreases j - i
{
  j - i < 2 || (s[i] == s[j - 1] && palindromic(s, i + 1, j - 1))
}

lemma /*{:_inductionTrigger palindromic(s, lo', hi'), palindromic(s, lo, hi)}*/ /*{:_induction s, lo, hi, lo', hi'}*/ lemma_palindromic_contains(s: string, lo: int, hi: int, lo': int, hi': int)
  requires 0 <= lo <= lo' <= hi' <= hi <= |s|
  requires lo + hi == lo' + hi'
  requires palindromic(s, lo, hi)
  ensures palindromic(s, lo', hi')
  decreases lo' - lo
{
  if lo < lo' {
    lemma_palindromic_contains(s, lo + 1, hi - 1, lo', hi');
  }
}

method expand_from_center(s: string, i0: int, j0: int)
    returns (lo: int, hi: int)
  requires 0 <= i0 <= j0 <= |s|
  requires palindromic(s, i0, j0)
  ensures 0 <= lo <= hi <= |s| && palindromic(s, lo, hi)
  ensures forall i: int, j: int {:trigger palindromic(s, i, j)} | 0 <= i <= j <= |s| && palindromic(s, i, j) && i + j == i0 + j0 :: j - i <= hi - lo
  decreases s, i0, j0
{
  lo, hi := i0, j0;
  while (lo - 1 >= 0 <== hi < |s|) && s[lo - 1] == s[hi]
    invariant 0 <= lo <= hi <= |s| && lo + hi == i0 + j0
    invariant palindromic(s, lo, hi)
  {
    lo, hi := lo - 1, hi + 1;
  }
  forall i: int, j: int | 0 <= i <= j <= |s| && i + j == i0 + j0 && j - i > hi - lo
    ensures !palindromic(s, i, j)
  {
    if palindromic(s, i, j) {
      lemma_palindromic_contains(s, i, j, lo - 1, hi + 1);
    }
  }
}

method longestPalindrome(s: string)
    returns (ans: string, lo: int, hi: int)
  ensures 0 <= lo <= hi <= |s| && ans == s[lo .. hi]
  ensures palindromic(s, lo, hi)
  ensures forall i: int, j: int {:trigger palindromic(s, i, j)} | 0 <= i <= j <= |s| && palindromic(s, i, j) :: j - i <= hi - lo
  decreases s
{
  lo, hi := 0, 0;
  for k: int := 0 to |s|
    invariant 0 <= lo <= hi <= |s|
    invariant palindromic(s, lo, hi)
    invariant forall i: int, j: int {:trigger palindromic(s, i, j)} | 0 <= i <= j <= |s| && i + j < 2 * k && palindromic(s, i, j) :: j - i <= hi - lo
  {
    var a, b := expand_from_center(s, k, k);
    if b - a > hi - lo {
      lo, hi := a, b;
    }
    var c, d := expand_from_center(s, k, k + 1);
    if d - c > hi - lo {
      lo, hi := c, d;
    }
  }
  return s[lo .. hi], lo, hi;
}

method {:vcs_split_on_every_assert} longestPalindrome'(s: string)
    returns (ans: string, lo: int, hi: int)
  ensures 0 <= lo <= hi <= |s| && ans == s[lo .. hi]
  ensures palindromic(s, lo, hi)
  ensures forall i: int, j: int {:trigger palindromic(s, i, j)} | 0 <= i <= j <= |s| && palindromic(s, i, j) :: j - i <= hi - lo
  decreases s
{
  var bogus: char :| true;
  var s' := insert_bogus_chars(s, bogus);
  var radii := new int[|s'|];
  var center, radius := 0, 0;
  ghost var loop_counter_outer, loop_counter_inner1, loop_counter_inner2 := 0, 0, 0;
  while center < |s'|
    invariant 0 <= center <= |s'|
    invariant forall c: int {:trigger radii[c]} | 0 <= c < center :: max_radius(s', c, radii[c])
    invariant center < |s'| ==> inbound_radius(s', center, radius) && palindromic_radius(s', center, radius)
    invariant center == |s'| ==> radius == 0
    invariant loop_counter_outer <= center
    invariant loop_counter_inner1 <= center + radius && loop_counter_inner2 <= center
    decreases |s'| - center
  {
    loop_counter_outer := loop_counter_outer + 1;
    while center - (radius + 1) >= 0 && center + radius + 1 < |s'| && s'[center - (radius + 1)] == s'[center + radius + 1]
      invariant inbound_radius(s', center, radius) && palindromic_radius(s', center, radius)
      invariant loop_counter_inner1 <= center + radius
      decreases center - radius
    {
      loop_counter_inner1 := loop_counter_inner1 + 1;
      radius := radius + 1;
    }
    lemma_end_of_expansion(s', center, radius);
    radii[center] := radius;
    var old_center, old_radius := center, radius;
    center := center + 1;
    radius := 0;
    while center <= old_center + old_radius
      invariant 0 <= center <= |s'|
      invariant forall c: int {:trigger radii[c]} | 0 <= c < center :: max_radius(s', c, radii[c])
      invariant center < |s'| ==> inbound_radius(s', center, radius) && palindromic_radius(s', center, radius)
      invariant loop_counter_inner2 <= center - 1
      decreases old_center + old_radius - center
    {
      loop_counter_inner2 := loop_counter_inner2 + 1;
      var mirrored_center := old_center - (center - old_center);
      var max_mirrored_radius := old_center + old_radius - center;
      lemma_mirrored_palindrome(s', old_center, old_radius, mirrored_center, radii[mirrored_center], center);
      if radii[mirrored_center] < max_mirrored_radius {
        radii[center] := radii[mirrored_center];
        center := center + 1;
      } else if radii[mirrored_center] > max_mirrored_radius {
        radii[center] := max_mirrored_radius;
        center := center + 1;
      } else {
        radius := max_mirrored_radius;
        break;
      }
    }
  }
  assert |s'| == 2 * |s| + 1;
  assert loop_counter_outer <= |s'|;
  assert loop_counter_inner1 <= |s'|;
  assert loop_counter_inner2 <= |s'|;
  var (c, r) := argmax(radii, 0);
  lo, hi := (c - r) / 2, (c + r) / 2;
  lemma_result_transfer(s, s', bogus, radii, c, r, hi, lo);
  return s[lo .. hi], lo, hi;
}

function {:opaque} insert_bogus_chars(s: string, bogus: char): (s': string)
  ensures |s'| == 2 * |s| + 1
  ensures forall i: int {:trigger s'[i * 2]} | 0 <= i <= |s| :: s'[i * 2] == bogus
  ensures forall i: int {:trigger s[i]} | 0 <= i < |s| :: s'[i * 2 + 1] == s[i]
  decreases s, bogus
{
  if s == "" then
    [bogus]
  else
    var s'_old: string := insert_bogus_chars(s[1..], bogus); var s'_new: seq<char> := [bogus] + [s[0]] + s'_old; assert forall i: int {:trigger s'_new[i * 2]} | 1 <= i <= |s| :: s'_new[i * 2] == s'_old[(i - 1) * 2]; s'_new
}

function {:opaque} argmax(a: array<int>, start: int): (res: (int, int))
  requires 0 <= start < a.Length
  reads a
  ensures start <= res.0 < a.Length && a[res.0] == res.1
  ensures forall i: int {:trigger a[i]} | start <= i < a.Length :: a[i] <= res.1
  decreases a.Length - start
{
  if start == a.Length - 1 then
    (start, a[start])
  else
    var (i: int, v: int) := argmax(a, start + 1); if a[start] >= v then (start, a[start]) else (i, v)
}

ghost predicate inbound_radius(s': string, c: int, r: int)
  decreases s', c, r
{
  r >= 0 &&
  0 <= c - r &&
  c + r < |s'|
}

ghost predicate palindromic_radius(s': string, c: int, r: int)
  requires inbound_radius(s', c, r)
  decreases s', c, r
{
  palindromic(s', c - r, c + r + 1)
}

ghost predicate max_radius(s': string, c: int, r: int)
  decreases s', c, r
{
  inbound_radius(s', c, r) &&
  palindromic_radius(s', c, r) &&
  forall r': int {:trigger palindromic_radius(s', c, r')} {:trigger inbound_radius(s', c, r')} | r' > r && inbound_radius(s', c, r') :: 
    !palindromic_radius(s', c, r')
}

lemma lemma_palindromic_radius_contains(s': string, c: int, r: int, r': int)
  requires inbound_radius(s', c, r) && palindromic_radius(s', c, r)
  requires 0 <= r' <= r
  ensures inbound_radius(s', c, r') && palindromic_radius(s', c, r')
  decreases s', c, r, r'
{
  lemma_palindromic_contains(s', c - r, c + r + 1, c - r', c + r' + 1);
}

lemma lemma_end_of_expansion(s': string, c: int, r: int)
  requires inbound_radius(s', c, r) && palindromic_radius(s', c, r)
  requires inbound_radius(s', c, r + 1) ==> s'[c - (r + 1)] != s'[c + r + 1]
  ensures max_radius(s', c, r)
  decreases s', c, r
{
  forall r': int | r' > r && inbound_radius(s', c, r')
    ensures !palindromic_radius(s', c, r')
  {
    if palindromic_radius(s', c, r') {
      lemma_palindromic_radius_contains(s', c, r', r + 1);
    }
  }
}

lemma lemma_mirrored_palindrome(s': string, c: int, r: int, c1: int, r1: int, c2: int)
  requires max_radius(s', c, r) && max_radius(s', c1, r1)
  requires c - r <= c1 < c < c2 <= c + r
  requires c2 - c == c - c1
  ensures c2 + r1 < c + r ==> max_radius(s', c2, r1)
  ensures c2 + r1 > c + r ==> max_radius(s', c2, c + r - c2)
  ensures c2 + r1 == c + r ==> palindromic_radius(s', c2, c + r - c2)
  decreases s', c, r, c1, r1, c2
{
  if c2 + r1 < c + r {
    for r2: int := 0 to r1
      invariant palindromic_radius(s', c2, r2)
    {
      ghost var r2' := r2 + 1;
      assert s'[c1 + r2'] == s'[c2 - r2'] by {
        lemma_palindromic_radius_contains(s', c, r, abs(c - c1 - r2'));
      }
      assert s'[c1 - r2'] == s'[c2 + r2'] by {
        lemma_palindromic_radius_contains(s', c, r, abs(c - c1 + r2'));
      }
      assert s'[c1 - r2'] == s'[c1 + r2'] by {
        lemma_palindromic_radius_contains(s', c1, r1, r2');
      }
    }
    ghost var r2' := r1 + 1;
    assert s'[c1 + r2'] == s'[c2 - r2'] by {
      lemma_palindromic_radius_contains(s', c, r, abs(c - c1 - r2'));
    }
    assert s'[c1 - r2'] == s'[c2 + r2'] by {
      lemma_palindromic_radius_contains(s', c, r, abs(c - c1 + r2'));
    }
    assert s'[c1 - r2'] != s'[c1 + r2'] by {
      assert !palindromic_radius(s', c1, r2');
    }
    lemma_end_of_expansion(s', c2, r1);
  } else {
    for r2: int := 0 to c + r - c2
      invariant palindromic_radius(s', c2, r2)
    {
      ghost var r2' := r2 + 1;
      assert s'[c1 + r2'] == s'[c2 - r2'] by {
        lemma_palindromic_radius_contains(s', c, r, abs(c - c1 - r2'));
      }
      assert s'[c1 - r2'] == s'[c2 + r2'] by {
        lemma_palindromic_radius_contains(s', c, r, abs(c - c1 + r2'));
      }
      assert s'[c1 - r2'] == s'[c1 + r2'] by {
        lemma_palindromic_radius_contains(s', c1, r1, r2');
      }
    }
    if c2 + r1 > c + r {
      ghost var r2' := c + r - c2 + 1;
      if inbound_radius(s', c, r + 1) {
        assert s'[c1 + r2'] == s'[c2 - r2'] by {
          lemma_palindromic_radius_contains(s', c, r, abs(c - c1 - r2'));
        }
        assert s'[c1 - r2'] != s'[c2 + r2'] by {
          assert !palindromic_radius(s', c, r + 1);
        }
        assert s'[c1 - r2'] == s'[c1 + r2'] by {
          lemma_palindromic_radius_contains(s', c1, r1, r2');
        }
        lemma_end_of_expansion(s', c2, c + r - c2);
      }
    }
  }
}

ghost function abs(x: int): int
  decreases x
{
  if x >= 0 then
    x
  else
    -x
}

lemma /*{:_inductionTrigger palindromic(s, lo, hi), argmax(radii, 0), insert_bogus_chars(s, bogus)}*/ /*{:_inductionTrigger palindromic(s, lo, hi), radii.Length, insert_bogus_chars(s, bogus)}*/ /*{:_induction s, bogus, radii, hi, lo}*/ lemma_result_transfer(s: string, s': string, bogus: char, radii: array<int>, c: int, r: int, hi: int, lo: int)
  requires s' == insert_bogus_chars(s, bogus)
  requires radii.Length == |s'|
  requires forall i: int {:trigger radii[i]} | 0 <= i < radii.Length :: max_radius(s', i, radii[i])
  requires (c, r) == argmax(radii, 0)
  requires lo == (c - r) / 2 && hi == (c + r) / 2
  ensures 0 <= lo <= hi <= |s|
  ensures palindromic(s, lo, hi)
  ensures forall i: int, j: int {:trigger palindromic(s, i, j)} | 0 <= i <= j <= |s| && palindromic(s, i, j) :: j - i <= hi - lo
  decreases s, s', bogus, radii, c, r, hi, lo
{
  forall k: int | 0 <= k < radii.Length
    ensures max_interval_for_same_center(s, k, (k - radii[k]) / 2, (k + radii[k]) / 2)
  {
    if (k + radii[k]) % 2 == 1 {
      lemma_palindrome_bogus(s, s', bogus, k, radii[k]);
    }
    ghost var lo, hi := (k - radii[k]) / 2, (k + radii[k]) / 2;
    lemma_palindrome_isomorph(s, s', bogus, lo, hi);
    forall i: int, j: int | 0 <= i <= j <= |s| && i + j == k && j - i > radii[k]
      ensures !palindromic(s, i, j)
    {
      lemma_palindrome_isomorph(s, s', bogus, i, j);
    }
  }
  for k: int := 0 to radii.Length - 1
    invariant forall i: int, j: int {:trigger palindromic(s, i, j)} | 0 <= i <= j <= |s| && palindromic(s, i, j) && i + j <= k :: j - i <= hi - lo
  {
    forall i: int, j: int | 0 <= i <= j <= |s| && palindromic(s, i, j) && i + j == k + 1
      ensures j - i <= hi - lo
    {
      ghost var k := k + 1;
      assert max_interval_for_same_center(s, k, (k - radii[k]) / 2, (k + radii[k]) / 2);
    }
  }
}

ghost predicate max_interval_for_same_center(s: string, k: int, lo: int, hi: int)
  decreases s, k, lo, hi
{
  0 <= lo <= hi <= |s| &&
  lo + hi == k &&
  palindromic(s, lo, hi) &&
  forall i: int, j: int {:trigger palindromic(s, i, j)} | 0 <= i <= j <= |s| && palindromic(s, i, j) && i + j == k :: 
    j - i <= hi - lo
}

lemma /*{:_inductionTrigger palindromic(s, lo, hi), insert_bogus_chars(s, bogus)}*/ /*{:_induction s, bogus, lo, hi}*/ lemma_palindrome_isomorph(s: string, s': string, bogus: char, lo: int, hi: int)
  requires s' == insert_bogus_chars(s, bogus)
  requires 0 <= lo <= hi <= |s|
  ensures palindromic(s, lo, hi) <==> palindromic_radius(s', lo + hi, hi - lo)
  decreases s, s', bogus, lo, hi
{
  if palindromic(s, lo, hi) {
    for r: int := 0 to hi - lo
      invariant palindromic_radius(s', lo + hi, r)
    {
      if (lo + hi - r) % 2 == 1 {
        lemma_palindrome_bogus(s, s', bogus, lo + hi, r);
      } else {
        ghost var i', j' := lo + hi - (r + 1), lo + hi + r + 1;
        ghost var i, j := i' / 2, j' / 2;
        assert s[i] == s[j] by {
          lemma_palindromic_contains(s, lo, hi, i, j + 1);
        }
      }
    }
  }
  if palindromic_radius(s', lo + hi, hi - lo) {
    ghost var lo', hi' := lo, hi;
    while lo' + 1 <= hi' - 1
      invariant lo <= lo' <= hi' <= hi
      invariant lo' + hi' == lo + hi
      invariant palindromic_radius(s', lo + hi, hi' - lo')
      invariant palindromic(s, lo', hi') ==> palindromic(s, lo, hi)
      decreases hi' - 1 - (lo' + 1)
    {
      assert palindromic_radius(s', lo + hi, hi' - lo' - 1);
      lo', hi' := lo' + 1, hi' - 1;
    }
  }
}

lemma /*{:_inductionTrigger insert_bogus_chars(s, bogus)}*/ /*{:_induction s, bogus}*/ lemma_palindrome_bogus(s: string, s': string, bogus: char, c: int, r: int)
  requires s' == insert_bogus_chars(s, bogus)
  requires inbound_radius(s', c, r) && palindromic_radius(s', c, r)
  requires (c + r) % 2 == 1
  ensures inbound_radius(s', c, r + 1) && palindromic_radius(s', c, r + 1)
  decreases s, s', bogus, c, r
{
  ghost var left, right := c - (r + 1), c + r + 1;
  assert left == left / 2 * 2;
  assert right == right / 2 * 2;
  assert s'[left] == s'[right] == bogus;
}
