import pytest

from dependencies import Depends, solve_dependent


@pytest.mark.anyio
async def test_depends():
    count = 0

    def get_values(values):
        nonlocal count
        count += 1
        return values

    async def get_length(values=Depends(get_values)):
        return len(values) or 1

    async def get_sum(values=Depends(get_values)):
        return sum(values)

    async def get_avg(sum=Depends(get_sum), length=Depends(get_length)):
        return sum / length

    values = (1, 2, 3)
    result = await solve_dependent(get_avg, values=values)

    assert result == 2
    assert count == 2


@pytest.mark.anyio
async def test_depends_use_cache():
    count = 0

    def get_values(values):
        nonlocal count
        count += 1
        return values

    async def get_length(values=Depends(get_values, use_cache=True)):
        return len(values) or 1

    async def get_sum(values=Depends(get_values, use_cache=True)):
        return sum(values)

    async def get_avg(sum=Depends(get_sum), length=Depends(get_length)):
        return sum / length

    values = (1, 2, 3)
    result = await solve_dependent(get_avg, values=values)
    assert result == 2
    assert count == 1
