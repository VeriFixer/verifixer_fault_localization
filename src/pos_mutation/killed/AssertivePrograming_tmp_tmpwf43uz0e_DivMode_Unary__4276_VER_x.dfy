// AssertivePrograming_tmp_tmpwf43uz0e_DivMode_Unary.dfy

ghost function UnaryToNat(x: Unary): nat
  decreases x
{
  match x
  case Zero() =>
    0
  case Suc(x') =>
    1 + UnaryToNat(x')
}

ghost function NatToUnary(n: nat): Unary
  decreases n
{
  if n == 0 then
    Zero
  else
    Suc(NatToUnary(n - 1))
}

lemma /*{:_inductionTrigger NatToUnary(UnaryToNat(x)), NatToUnary(n)}*/ /*{:_inductionTrigger UnaryToNat(x), UnaryToNat(NatToUnary(n))}*/ /*{:_induction n, x}*/ NatUnaryCorrespondence(n: nat, x: Unary)
  ensures UnaryToNat(NatToUnary(n)) == n
  ensures NatToUnary(UnaryToNat(x)) == x
  decreases n, x
{
}

predicate Less(x: Unary, y: Unary)
  decreases x, y
{
  y != Zero &&
  (x.Suc? ==>
    Less(x.pred, y.pred))
}

predicate LessAlt(x: Unary, y: Unary)
  decreases x, y
{
  y != Zero &&
  (x == Zero || Less(x.pred, y.pred))
}

lemma /*{:_inductionTrigger LessAlt(x, y)}*/ /*{:_inductionTrigger Less(x, y)}*/ /*{:_induction x, y}*/ LessSame(x: Unary, y: Unary)
  ensures Less(x, y) == LessAlt(x, y)
  decreases x, y
{
}

lemma /*{:_inductionTrigger UnaryToNat(y), UnaryToNat(x)}*/ /*{:_inductionTrigger Less(x, y)}*/ /*{:_induction x, y}*/ LessCorrect(x: Unary, y: Unary)
  ensures Less(x, y) <==> UnaryToNat(x) < UnaryToNat(y)
  decreases x, y
{
}

lemma /*{:_inductionTrigger Less(x, z), Less(y, z)}*/ /*{:_inductionTrigger Less(y, z), Less(x, y)}*/ /*{:_induction x, y, z}*/ LessTransitive(x: Unary, y: Unary, z: Unary)
  requires Less(x, y) && Less(y, z)
  ensures Less(x, z)
  decreases x, y, z
{
}

function Add(x: Unary, y: Unary): Unary
  decreases x, y
{
  match y
  case Zero() =>
    x
  case Suc(y') =>
    Suc(Add(x, y'))
}

lemma {:induction false} SucAdd(x: Unary, y: Unary)
  ensures Suc(Add(x, y)) == Add(Suc(x), y)
  decreases x, y
{
  match y
  case {:split false} Zero() =>
  case {:split false} Suc(y') =>
    calc {
      Suc(Add(x, Suc(y')));
    ==
      Suc(Suc(Add(x, y')));
    ==
      {
        SucAdd(x, y');
      }
      Suc(Add(Suc(x), y'));
    ==
      Add(Suc(x), Suc(y'));
    }
}

lemma {:induction false} AddZero(x: Unary)
  ensures Add(Zero, x) == x
  decreases x
{
  match x
  case {:split false} Zero() =>
  case {:split false} Suc(x') =>
    calc {
      Add(Zero, Suc(x'));
    ==
      Suc(Add(Zero, x'));
    ==
      {
        AddZero(x');
      }
      Suc(x');
    }
}

function Sub(x: Unary, y: Unary): Unary
  requires !Less(x, y)
  decreases x, y
{
  match y
  case Zero() =>
    x
  case Suc(y') =>
    Sub(x.pred, y')
}

function Mul(x: Unary, y: Unary): Unary
  decreases x, y
{
  match x
  case Zero() =>
    Zero
  case Suc(x') =>
    Add(Mul(x', y), y)
}

lemma /*{:_inductionTrigger Sub(x, y)}*/ /*{:_inductionTrigger Less(x, y)}*/ /*{:_induction x, y}*/ SubStructurallySmaller(x: Unary, y: Unary)
  requires !Less(x, y) && y != Zero
  ensures Sub(x, y) < x
  decreases x, y
{
}

lemma /*{:_inductionTrigger Sub(x, y)}*/ /*{:_inductionTrigger Less(x, y)}*/ /*{:_induction x, y}*/ AddSub(x: Unary, y: Unary)
  requires !Less(x, y)
  ensures Add(Sub(x, y), y) == x
  decreases x, y
{
}

method {:verify false} IterativeDivMod'(x: Unary, y: Unary)
    returns (d: Unary, m: Unary)
  requires y != Zero
  ensures Add(Mul(d, y), m) == x && Less(m, y)
  decreases x, y
{
  if Less(x, y) {
    d := Zero;
    m := x;
  } else {
    var x0: Unary := x;
    d := Zero;
    while !Less(x0, y)
      invariant Add(Mul(d, y), x0) == x
      decreases x0
    {
      d := Suc(d);
      x0 := Sub(x0, y);
    }
    m := x0;
  }
}

method IterativeDivMod(x: Unary, y: Unary)
    returns (d: Unary, m: Unary)
  requires y != Zero
  ensures Add(Mul(d, y), m) == x && Less(m, y)
  decreases x, y
{
  if Less(x, y) {
    assert Less(x, y);
    AddZero(x);
    assert Add(Zero, x) == x;
    assert Mul(Zero, y) == Zero;
    assert Add(Mul(Zero, y), x) == x;
    d := Zero;
    m := x;
    assert Add(Mul(d, y), m) == m;
    assert Less(m, y);
    assert Add(Mul(d, y), m) == x && Less(m, y);
  } else {
    assert !Less(x, y);
    assert y != Zero;
    var x0: Unary := x;
    assert Mul(Zero, y) == Zero;
    d := Zero;
    assert Mul(d, y) == Zero;
    AddZero(x);
    assert Add(Zero, x) == x;
    assert Add(Mul(d, y), x) == x;
    assert Add(Mul(d, y), x0) == x;
    while !Less(x0, y)
      invariant Add(Mul(d, y), x0) == x
      decreases x0
    {
      assert Add(Mul(d, y), x0) == x;
      assert !Less(x0, y);
      assert y != Zero;
      AddMulSucSubEqAddMul(x, y, x0);
      assert Add(Mul(Suc(d), y), Sub(x0, y)) == Add(Mul(d, y), x0);
      assert Add(Mul(Suc(d), y), Sub(x0, y)) == x;
      d := Suc(d);
      assert !Less(x0, y) && y != Zero;
      SubStructurallySmaller(x0, y);
      assert Sub(x0, y) < x0;
      x0 := Sub(x0, y);
      assert Add(Mul(d, y), x0) == x;
    }
    assert Add(Mul(d, y), x0) == x;
    m := x0;
    assert Add(Mul(d, y), m) == x;
  }
  assert Add(Mul(d, y), m) == x;
}

lemma /*{:_inductionTrigger Add(Mul(a, b), b)}*/ /*{:_inductionTrigger Mul(Unary.Suc(a), b)}*/ /*{:_induction a, b}*/ AddMulEqMulSuc(a: Unary, b: Unary)
  ensures Mul(Suc(a), b) == Add(Mul(a, b), b)
  decreases a, b
{
  calc {
    Mul(Suc(a), b);
  ==
    Add(Mul(a, b), b);
  }
}

lemma /*{:_inductionTrigger Sub(x0, y), Unary.Suc(d)}*/ /*{:_inductionTrigger Unary.Suc(d), Less(x0, y)}*/ /*{:_induction d, y, x0}*/ AddMulSucSubEqAddMul(d: Unary, y: Unary, x0: Unary)
  requires !Less(x0, y)
  requires y != Zero
  ensures Add(Mul(Suc(d), y), Sub(x0, y)) == Add(Mul(d, y), x0)
  decreases d, y, x0
{
  calc {
    Add(Mul(Suc(d), y), Sub(x0, y));
  ==
    {
      AddMulEqMulSuc(d, y);
      assert Mul(Suc(d), y) == Add(Mul(d, y), y);
    }
    Add(Add(Mul(d, y), y), Sub(x0, y));
  ==
    {
      AddTransitive(Mul(d, y), y, Sub(x0, y));
      assert Add(Mul(d, y), Add(y, Sub(x0, y))) == Add(Add(Mul(d, y), y), Sub(x0, y));
    }
    Add(Mul(d, y), Add(y, Sub(x0, y)));
  ==
    {
      AddCommutative(Sub(x0, y), y);
      assert Add(Sub(x0, y), y) == Add(y, Sub(x0, y));
    }
    Add(Mul(d, y), Add(Sub(x0, y), y));
  ==
    {
      assert !Less(x0, y);
      AddSub(x0, y);
      assert Add(Sub(x0, y), y) == x0;
    }
    Add(Mul(d, y), x0);
  }
}

lemma /*{:_inductionTrigger Add(Add(a, b), c)}*/ /*{:_inductionTrigger Add(a, Add(b, c))}*/ /*{:_induction a, b, c}*/ AddTransitive(a: Unary, b: Unary, c: Unary)
  ensures Add(a, Add(b, c)) == Add(Add(a, b), c)
  decreases a, b, c
{
  match c
  case {:split false} Zero() =>
    calc {
      Add(a, Add(b, c));
    ==
      Add(a, Add(b, Zero));
    ==
      Add(a, b);
    ==
      Add(Add(a, b), Zero);
    ==
      Add(Add(a, b), c);
    }
  case {:split false} Suc(c') =>
    match b
    case {:split false} Zero() =>
      calc {
        Add(a, Add(b, c));
      ==
        Add(a, Add(Zero, Suc(c')));
      ==
        {
          AddZero(Suc(c'));
          assert Add(Zero, Suc(c')) == Suc(c');
        }
        Add(a, Suc(c'));
      ==
        Add(Add(a, Zero), Suc(c'));
      ==
        Add(Add(a, b), Suc(c'));
      ==
        Add(Add(a, b), c);
      }
    case {:split false} Suc(b') =>
      match a
      case {:split false} Zero() =>
        calc {
          Add(a, Add(b, c));
        ==
          Add(Zero, Add(Suc(b'), Suc(c')));
        ==
          {
            AddZero(Add(Suc(b'), Suc(c')));
            assert Add(Zero, Add(Suc(b'), Suc(c'))) == Add(Suc(b'), Suc(c'));
          }
          Add(Suc(b'), Suc(c'));
        ==
          {
            AddZero(Suc(b'));
            assert Add(Zero, Suc(b')) == Suc(b');
          }
          Add(Add(Zero, Suc(b')), Suc(c'));
        ==
          Add(Add(a, b), c);
        }
      case {:split false} Suc(a') =>
        calc {
          Add(a, Add(b, c));
        ==
          Add(Suc(a'), Add(Suc(b'), Suc(c')));
        ==
          Add(Suc(a'), Suc(Add(Suc(b'), c')));
        ==
          Suc(Add(Suc(a'), Add(Suc(b'), c')));
        ==
          {
            SucAdd(a', Add(Suc(b'), c'));
            assert Suc(Add(a', Add(Suc(b'), c'))) == Add(Suc(a'), Add(Suc(b'), c'));
          }
          Suc(Suc(Add(a', Add(Suc(b'), c'))));
        ==
          {
            SucAdd(b', c');
            assert Suc(Add(b', c')) == Add(Suc(b'), c');
          }
          Suc(Suc(Add(a', Suc(Add(b', c')))));
        ==
          Suc(Suc(Suc(Add(a', Add(b', c')))));
        ==
          {
            AddTransitive(a', b', c');
            assert Add(a', Add(b', c')) == Add(Add(a', b'), c');
          }
          Suc(Suc(Suc(Add(Add(a', b'), c'))));
        ==
          Suc(Suc(Add(Add(a', b'), Suc(c'))));
        ==
          {
            SucAdd(Add(a', b'), Suc(c'));
            assert Suc(Add(Add(a', b'), Suc(c'))) == Add(Suc(Add(a', b')), Suc(c'));
          }
          Suc(Add(Suc(Add(a', b')), Suc(c')));
        ==
          {
            SucAdd(a', b');
            assert Suc(Add(a', b')) == Add(Suc(a'), b');
          }
          Suc(Add(Add(Suc(a'), b'), Suc(c')));
        ==
          {
            SucAdd(Add(Suc(a'), b'), Suc(c'));
            assert Suc(Add(Add(Suc(a'), b'), Suc(c'))) == Add(Suc(Add(Suc(a'), b')), Suc(c'));
          }
          Add(Suc(Add(Suc(a'), b')), Suc(c'));
        ==
          Add(Add(Suc(a'), Suc(b')), Suc(c'));
        ==
          Add(Add(a, b), c);
        }
}

lemma /*{:_inductionTrigger Add(b, a)}*/ /*{:_inductionTrigger Add(a, b)}*/ /*{:_induction a, b}*/ AddCommutative(a: Unary, b: Unary)
  ensures Add(a, b) == Add(b, a)
  decreases a, b
{
  match b
  case {:split false} Zero() =>
    calc {
      Add(a, b);
    ==
      Add(a, Zero);
    ==
      a;
    ==
      {
        AddZero(a);
        assert Add(Zero, a) == a;
      }
      Add(Zero, a);
    ==
      Add(b, a);
    }
  case {:split false} Suc(b') =>
    calc {
      Add(a, b);
    ==
      Add(a, Suc(b'));
    ==
      Suc(Add(a, b'));
    ==
      {
        AddCommutative(a, b');
        assert Add(a, b') == Add(b', a);
      }
      Suc(Add(b', a));
    ==
      {
        SucAdd(b', a);
        assert Suc(Add(b', a)) == Add(Suc(b'), a);
      }
      Add(Suc(b'), a);
    ==
      Add(b, a);
    }
}

method Main()
{
  var U3 := Suc(Suc(Suc(Zero)));
  assert UnaryToNat(U3) == 3;
  var U7 := Suc(Suc(Suc(Suc(U3))));
  assert UnaryToNat(U7) == 7;
  var d, m := IterativeDivMod(U7, U3);
  assert Add(Mul(d, U3), m) == U7 && Less(m, U3);
  print "Just as 7 divided by 3 is 2 with a remainder of 1, IterativeDivMod(", U7, ", ", U3, ") is ", d, " with a remainder of ", m;
}

datatype Unary = Zero | Suc(pred: Unary)
