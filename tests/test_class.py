import pytest

from dependencies.dependencies import Depends, solve_dependent


@pytest.mark.anyio
async def test_class_dependencies():
    class User:
        def __init__(
            self,
            name: str,
        ):
            self.name = name

    name = "test"
    user = await solve_dependent(User, name=name)
    assert user.name == name


@pytest.mark.anyio
async def test_class_depends():
    def get_name():
        return "test"

    class User:
        def __init__(self, name=Depends(get_name)):
            self.name = name

    user: User = await solve_dependent(User)
    assert user.name == get_name()


@pytest.mark.anyio
async def test_var_namespace():
    class User:
        def __init__(self, name):
            self.name = name

    user = await solve_dependent(User, var_namespace=lambda: {"name": "test"})

    assert user.name == "test"
