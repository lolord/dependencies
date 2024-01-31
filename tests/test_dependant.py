import pytest

from dependencies import get_dependent, solve_dependent


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def data(self):
        return {"x": self.x, "y": self.y}


data = {"x": 1, "y": 2}


def get_kwargs():
    return data


@pytest.mark.anyio
async def test_dependent():
    dependent = get_dependent(call=Point)
    user = await solve_dependent(dependent, **data)  # type: ignore
    assert user.data() == data


@pytest.mark.anyio
async def test_dependent_var_namespace():
    dependent = get_dependent(call=Point)
    dependent.var_namespace = get_kwargs
    user = await solve_dependent(dependent)
    assert user.data() == data
