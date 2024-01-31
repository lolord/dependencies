# dependencies

## Introduce

`dependencies` is a python library for resolving parameter dependency

## Feature

- Parameter dependency parsing
- Support class and pydantic.BaseModel dependencies
- Sub dependency
- Asynchronous

## Requirements

Python 3.11 or above.

## Installation

pip install git+https://gitee.com/lolord/dependencies.git

## Usage

``` python
from typing import Dict, List

import anyio
from pydantic import BaseModel

from dependencies import Depends, decorator


class User(BaseModel):
    name: str
    score: int


@decorator
def create_user(user: User = Depends()) -> User:
    return user


async def get_users(users: List[Dict]) -> List[User]:
    results: List[User] = []
    for user in users:
        results.append(await create_user(**user))
    return results


async def length(users: List[User] = Depends(get_users, use_cache=True)):
    return len(users) or 1


async def sum_score(users: List[User] = Depends(get_users, use_cache=True)):
    return sum(user.score for user in users)


@decorator
async def avg(sum=Depends(sum_score), length=Depends(length)):
    return sum / length


async def main():
    user = await create_user(name="Tom", score=90)
    assert user.name == "Tom"
    assert user.score == 90

    users = [{"name": "Tom", "score": 90}, {"name": "Bob", "score": 80}]
    assert await avg(users=users) == 85

```