import pytest

from dependencies.dependencies import apply_parameter


def test_positional():
    def foo(a, b, /, c):
        return a, b, c

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": 3})
    assert a == (1, 2, 3)
    assert b == {}
    assert foo(*a, **b) == (1, 2, 3)


def test_var_positional():
    def foo(a, b, *c):
        return a, b, c

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": (3, 4)})
    assert a == (1, 2, 3, 4)
    assert b == {}
    assert foo(*a, **b) == (1, 2, (3, 4))
    with pytest.raises(TypeError, match=".* is not iterable: .*"):
        a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": 3})

    def foo(a, b, *args):
        return a, b, args

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "args": (3, 4)})
    assert a == (1, 2, 3, 4)
    assert b == {}
    assert foo(*a, **b) == (1, 2, (3, 4))

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": (3, 4)})

    assert a == (
        1,
        2,
    )
    assert b == {}
    assert foo(*a, **b) == (1, 2, ())


def test_keywords():
    def foo(a, b, c=None, d=4):
        return a, b, c, d

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": 3})
    assert a == (1, 2, 3, 4)
    assert b == {}
    assert foo(*a, **b) == (1, 2, 3, 4)


def test_var_keywords():
    def foo(a, b, **c):
        return a, b, c

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": {"d": "e"}})
    assert a == (1, 2)
    assert b == {"d": "e"}
    assert foo(*a, **b) == (1, 2, {"d": "e"})

    def foo(a, b, **kwargs):
        return a, b, kwargs

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": {"d": "e"}})
    assert a == (1, 2)
    assert b == {"c": {"d": "e"}}
    assert foo(*a, **b) == (1, 2, {"c": {"d": "e"}})


def test_not_find_parameter():
    def foo(a, b, **c):  # pragma: no cover
        return a, b, c

    assert apply_parameter(foo, {"a": 1, "b": 2, "c": {"d": "e"}}) == (
        (1, 2),
        {"d": "e"},
    )
    with pytest.raises(ValueError):
        apply_parameter(foo, {})


def test_var_keyword_typeerror():
    def foo(a, b, **c):  # pragma: no cover
        return a, b, c

    assert apply_parameter(foo, {"a": 1, "b": 2, "c": {"d": "e"}}) == (
        (1, 2),
        {"d": "e"},
    )
    with pytest.raises(TypeError, match=".* is a VAR_KEYWORD: .*"):
        apply_parameter(foo, {"a": 1, "b": 2, "c": 3})


if __name__ == "__main__":  # pragma: no cover
    test_positional()
    test_var_positional()
    test_keywords()
    test_var_keywords()
    test_not_find_parameter()
    test_var_keyword_typeerror()
