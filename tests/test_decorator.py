from typing import Annotated

import pytest

from dependencies import Depends, decorator


def width(w):
    return w


async def height(h):
    return h


@decorator
async def area(
    width: Annotated[int, Depends(width)], height: Annotated[int, Depends(height)]
):
    return width * height


@pytest.mark.anyio
async def test_decorator():
    w, h = 2, 3
    assert w * h == await area(w=w, h=h)
