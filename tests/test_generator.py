from contextlib import AsyncExitStack

import pytest

from dependencies import Depends, solve_dependent

count = 0


def generator():
    global count
    try:
        yield 1
    finally:
        count += 1


async def async_generator():
    global count
    try:
        yield 2
    finally:
        count += 1


def apply(g=Depends(generator)):
    return g


async def async_apply(g=Depends(async_generator)):
    return g


@pytest.mark.anyio
async def test():
    result = await solve_dependent(apply)
    assert result == 1
    assert count == 1
    async with AsyncExitStack() as stack:
        result = await solve_dependent(async_apply, stack=stack)
        assert result == 2
        assert count == 1
    assert count == 2
