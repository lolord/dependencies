import pytest

from dependencies import Depends, solve_dependent


class Functor:
    async def __call__(self, a, b="b", c=Depends(lambda: "c")):
        return (a, b, c)


@pytest.mark.anyio
async def test_functor():  # pragma: no cover
    functor = Functor()

    assert await solve_dependent(functor, a="a") == ("a", "b", "c")
