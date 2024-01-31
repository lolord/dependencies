from typing import Annotated, Optional, TypedDict

import pytest

from dependencies.dependencies import Dependent, Depends, solve_dependent


def get_user(user: Annotated["User", Depends()]):
    return user


def get_optional_user(user: Annotated[Optional["User"], Depends()]):
    return user


class User:
    def __init__(self, name) -> None:
        self.name = name


@pytest.mark.anyio
async def test_forwardref():
    bob = await solve_dependent(get_user, name="Bob")
    assert type(bob) == User
    assert bob.name == "Bob"

    alice = await solve_dependent(get_optional_user, name="Alice")
    assert type(alice) == User
    assert alice.name == "Alice"


@pytest.mark.anyio
async def test_annotated():
    def get_bob_name(user: Annotated[User, Depends()]):
        return user.name

    name = await solve_dependent(get_bob_name, name="Bob")
    assert name == "Bob"

    def get_alice_name(user: Annotated[User, Depends(get_user)]):
        return user.name

    name = await solve_dependent(get_alice_name, name="Alice")
    assert name == "Alice"


@pytest.mark.anyio
async def test_dict():
    x, y = 1, 2
    point = await solve_dependent(
        dict,
        dependencies=[Dependent(lambda: x, name="x"), Dependent(lambda: y, name="y")],
    )
    assert point == dict(x=x, y=y)


@pytest.mark.anyio
async def test_typed_dict():
    class Point2D(TypedDict):
        x: int
        y: int

    x, y = 1, 2
    point = await solve_dependent(Point2D, x=x, y=y)
    assert point == dict(x=x, y=y)
