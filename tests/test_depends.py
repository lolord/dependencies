from typing import Annotated

import pytest

from dependencies import Depends, solve_dependent


@pytest.mark.anyio
async def test_depends():
    count = 0

    def get_values(values):
        nonlocal count
        count += 1
        return values

    async def get_length(values: Annotated[tuple[int, ...], Depends(get_values)]):
        return len(values) or 1

    async def get_sum(values: Annotated[tuple[int, ...], Depends(get_values)]):
        return sum(values)

    async def get_avg(
        sum: Annotated[int, Depends(get_sum)],
        length: Annotated[int, Depends(get_length)],
    ):
        return sum / length

    values = (1, 2, 3)
    result = await solve_dependent(get_avg, values=values)

    assert result == 2
    assert count == 2
