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

    args, kwargs = apply_parameter(foo, {"a": 1, "b": 2, "c": (3, 4)})
    assert args == (1, 2, 3, 4)
    assert kwargs == {}
    assert foo(*args, **kwargs) == (1, 2, (3, 4))

    args, kwargs = apply_parameter(foo, {"a": 1, "b": 2, "c": (3, 4), "d": 5})
    assert args == (1, 2, 3, 4)
    assert kwargs == {}

    args, kwargs = apply_parameter(foo, {"a": 1, "b": 2, "c": (), "d": 5})
    assert args == (1, 2)
    assert kwargs == {}

    args, kwargs = apply_parameter(foo, {"a": 1, "b": 2, "d": 5})
    assert args == (1, 2)
    assert kwargs == {}

    with pytest.raises(TypeError, match=".* is not iterable: .*"):
        apply_parameter(foo, {"a": 1, "b": 2, "c": 3})


def test_keywords():
    def foo(a, b, c=None, d=4):
        return a, b, c, d

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": 3})
    assert a == (1, 2, 3, 4)
    assert b == {}
    assert foo(*a, **b) == (1, 2, 3, 4)


def test_var_keywords():
    def foo(a, b, **kwargs):
        return a, b, kwargs

    a, b = apply_parameter(foo, {"a": 1, "b": 2, "c": 3, "d": 4})
    assert a == (1, 2)
    assert b == {"c": 3, "d": 4}
    assert foo(*a, **b) == (1, 2, {"c": 3, "d": 4})


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
