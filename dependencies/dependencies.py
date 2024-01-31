import functools
import inspect
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from types import NoneType
from typing import (
    Annotated,
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    ContextManager,
    Coroutine,
    Dict,
    ForwardRef,
    Generic,
    Hashable,
    Iterator,
    List,
    Optional,
    ParamSpec,
    Tuple,
    TypeAlias,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    is_typeddict,
)

import anyio
from anyio.to_thread import run_sync

P = ParamSpec("P")
R = TypeVar("R")


DependentCall: TypeAlias = Callable[..., R]


def get_dict_signature(cls: Any) -> Optional[inspect.Signature]:
    typed_params: List[inspect.Parameter] = []
    if inspect.isclass(cls):
        if is_typeddict(cls):
            typed_params.extend(
                inspect.Parameter(
                    name=name,
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    default=inspect.Parameter.empty,
                    annotation=annotation,
                )
                for name, annotation in cls.__annotations__.items()
            )

        elif issubclass(cls, dict):
            typed_params.append(
                inspect.Parameter(
                    name="kwargs",
                    kind=inspect.Parameter.VAR_KEYWORD,
                    default=inspect.Parameter.empty,
                    annotation=inspect.Parameter.empty,
                )
            )

    return inspect.Signature(typed_params) if typed_params else None


def get_functor_signature(functor: Any) -> Optional[inspect.Signature]:
    """functor is a callable class instance"""
    if (
        hasattr(functor, "__call__")
        and not inspect.isfunction(functor)
        and not inspect.isclass(functor)
    ):
        return inspect.Signature.from_callable(functor)
    return None


def get_typed_signature(call: Callable[..., Any]) -> inspect.Signature:
    signature = get_functor_signature(call)
    if signature is None:
        signature = get_dict_signature(call)
    if signature is None:
        # default signature
        signature = inspect.signature(call)
    if inspect.isclass(call):
        globalns = getattr(call.__init__, "__globals__", {})
    else:
        globalns = getattr(call, "__globals__", {})
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_typed_annotation(param.annotation, globalns),
        )
        for param in signature.parameters.values()
    ]
    typed_signature = inspect.Signature(typed_params)
    return typed_signature


def _make_key(
    dependent: "Dependent", args: Tuple[Any, ...], kwargs: Dict[str, Any]
) -> Hashable:
    # fixed keywords
    return (dependent.call, dependent.name)


class Dependent(Generic[R]):
    def __init__(
        self,
        call: DependentCall[R],
        *,
        name: Optional[str] = None,
        dependencies: Optional[List["Dependent"]] = None,
        use_cache: bool = False,
        var_namespace: Optional[Callable[[], Dict[str, Any]]] = None,
        make_key: Callable[..., Hashable] = _make_key,
    ) -> None:
        self.name = name
        self.dependencies = dependencies or []
        self.call = call
        self.__signature = None
        self.use_cache = use_cache
        self.make_key = make_key
        self.var_namespace = var_namespace

    @property
    def signature(self):
        if self.__signature is None:
            self.__signature = get_typed_signature(self.call)
        return self.__signature

    def __str__(self):  # pragma: no cover
        return (
            f"{self.__class__.__name__}(call={self.call},name={self.name},"
            + f"dependencies={[str(d) for d in self.dependencies]},use_cache={self.use_cache})"
        )


class Depends(Generic[R]):
    __slots__ = ("dependency", "use_cache", "default")

    def __init__(
        self,
        dependency: Optional[DependentCall[R]] = None,
        *,
        default: Optional[Any] = None,
        use_cache: bool = False,
    ):
        self.dependency = dependency
        self.use_cache = use_cache
        self.default = default

    def __str__(self) -> str:  # pragma: no cover
        attr = getattr(self.dependency, "__name__", type(self.dependency).__name__)
        cache = "" if self.use_cache else "use_cache=False"
        default = f"default={self.default}" if self.default else ""
        return f"{self.__class__.__name__}({attr}, {cache}, {default})"


async def run_in_threadpool(func: DependentCall[R], *args: Any, **kwargs: Any) -> R:
    if kwargs:
        func = functools.partial(func, **kwargs)
    return await run_sync(func, *args)


_CM_T = TypeVar("_CM_T")


@asynccontextmanager
async def contextmanager_in_threadpool(
    cm: ContextManager[_CM_T],
) -> AsyncGenerator[_CM_T, None]:
    # blocking __exit__ from running waiting on a free thread
    # can create race conditions/deadlocks if the context manager itself
    # has it's own internal pool (e.g. a database connection pool)
    # to avoid this we let __exit__ run without a capacity limit
    # since we're creating a new limiter for each call, any non-zero limit
    # works (1 is arbitrary)
    exit_limiter = anyio.CapacityLimiter(1)
    try:
        yield await run_in_threadpool(cm.__enter__)
    except Exception as e:  # pragma: no cover
        ok = bool(await run_sync(cm.__exit__, type(e), e, None, limiter=exit_limiter))
        if not ok:
            raise e
    else:
        await run_sync(cm.__exit__, None, None, None, limiter=exit_limiter)


def evaluate_forwardref(
    type_: ForwardRef, globalns: Any = None, localns: Any = None
) -> Any:
    # Even though it is the right signature for python 3.9, mypy complains with
    # `error: Too many arguments for "_evaluate" of "ForwardRef"` hence the cast...
    return cast(Any, type_)._evaluate(globalns, localns, set())


def get_typed_annotation(annotation: Any, globalns: Dict[str, Any]) -> Any:
    if get_origin(annotation) is Union:
        # annotation is typing.Optional[Any]
        annotation, *_others = get_args(annotation)
        assert _others == [NoneType]
    elif isinstance(annotation, str):
        # str will automatically convert to ForwardRef
        annotation = ForwardRef(annotation)
    if isinstance(annotation, ForwardRef):
        annotation = evaluate_forwardref(annotation, globalns, {})
    return annotation


def get_sub_dependent(name, annotation, depends: Depends[R]) -> Dependent[R]:
    dependency: Callable[..., R] = (
        depends.dependency if depends.dependency else annotation
    )

    return get_dependent(
        call=dependency,
        name=name,
        use_cache=depends.use_cache,
    )


def get_dependent(
    call: Union[DependentCall[R], Dependent[R]],
    *,
    name: Optional[str] = None,
    use_cache: bool = True,
) -> Dependent[R]:
    if isinstance(call, Dependent):
        return call
    dependent = Dependent(call=call, name=name, use_cache=use_cache)
    signature_params = dependent.signature.parameters
    for _, param in signature_params.items():
        depends: Optional[Depends] = None
        annotation = param.annotation
        if get_origin(param.annotation) is Annotated:
            annotation, *items = get_args(param.annotation)
            annotation = get_typed_annotation(
                annotation, globalns=getattr(call, "__globals__", {})
            )
            for depends in items:
                if isinstance(depends, Depends):
                    # Annotated[User, Depends(get_user)]
                    # Annotated[User, Depends()]
                    if depends.dependency is None:
                        depends.dependency = annotation
                    continue
        if depends and isinstance(param.default, Depends):  # pragma: no cover
            raise ValueError(
                f"{param.name} have two depends:{ depends}, {param.default}"
            )

        depends = depends or param.default
        if isinstance(depends, Depends):
            sub_dependent = get_sub_dependent(
                name=param.name,
                annotation=get_typed_annotation(
                    annotation, globalns=getattr(call, "__globals__", {})
                ),
                depends=depends,
            )
            dependent.dependencies.append(sub_dependent)

    return dependent


def is_coroutine_callable(call: Callable[..., Any]) -> bool:
    if inspect.isroutine(call):
        return inspect.iscoroutinefunction(call)
    if inspect.isclass(call):
        return False
    _call = getattr(call, "__call__", None)
    return inspect.iscoroutinefunction(_call)


def is_async_gen_callable(call: Callable[..., Any]) -> bool:
    if inspect.isasyncgenfunction(call):
        return True
    _call = getattr(call, "__call__", None)
    return inspect.isasyncgenfunction(_call)


def is_gen_callable(call: Callable[..., Any]) -> bool:
    if inspect.isgeneratorfunction(call):
        return True
    _call = getattr(call, "__call__", None)
    return inspect.isgeneratorfunction(_call)


def lookup_value(
    param: inspect.Parameter,
    values: Dict[str, Any],
    namespace: Optional[Dict[str, Any]] = None,
):
    if param.name in values:
        return values.pop(param.name)
    if namespace is not None and param.name in namespace:
        return namespace.get(param.name)
    elif param.default != inspect.Parameter.empty:
        # Assign a value to the parameter even if there is a default value
        return param.default
    else:
        raise ValueError(f"{param.name} is not find")


def apply_parameter(
    dependent: Union[Dependent, Callable],
    values: Dict[str, Any],
    namespace: Optional[Dict[str, Any]] = None,
):
    dependent = (
        dependent if isinstance(dependent, Dependent) else get_dependent(call=dependent)
    )
    keywords = {}
    positional = []
    for param in dependent.signature.parameters.values():
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            positional.append(lookup_value(param, values, namespace))
        elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            positional.append(lookup_value(param, values, namespace))
        elif param.kind == inspect.Parameter.VAR_POSITIONAL:
            if param.name in values:
                value = values.pop(param.name)
                if isinstance(value, (tuple, list)):
                    positional += value
                else:
                    raise TypeError(f"{param.name} is not iterable: {repr(value)}")
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            keywords[param.name] = lookup_value(param, values, namespace)
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            if param.name in values:
                value = values[param.name]
                if isinstance(value, dict):
                    keywords.update(**value)
                else:
                    raise TypeError(f"{param.name} is a VAR_KEYWORD: {value}")
            else:
                keywords.update(values)
    return tuple(positional), keywords


async def solve_generator(
    *,
    call: Union[Callable[..., Iterator[R]], Callable[..., AsyncIterator[R]]],
    stack: AsyncExitStack,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> R:
    if is_gen_callable(call):
        call = cast(Callable[..., Iterator[R]], call)
        cm = contextmanager_in_threadpool(contextmanager(call)(*args, **kwargs))
    elif is_async_gen_callable(call):
        call = cast(Callable[..., AsyncIterator[R]], call)
        cm = asynccontextmanager(call)(*args, **kwargs)
    else:  # pragma: no cover
        raise TypeError(f"call is not a generator:{type(call)}")
    result = await stack.enter_async_context(cm)

    return cast(R, result)


async def apply(
    call: Callable,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
    stack: AsyncExitStack,
) -> Any:
    if is_gen_callable(call) or is_async_gen_callable(call):
        return await solve_generator(call=call, stack=stack, args=args, kwargs=kwargs)
    elif is_coroutine_callable(call):
        call = cast(Callable[..., Coroutine], call)
        return await call(*args, **kwargs)
    else:
        return await run_in_threadpool(call, *args, **kwargs)


async def solve_dependencies(
    *,
    dependent: Dependent,
    stack: AsyncExitStack,
    namespace: Optional[Dict[str, Any]] = None,
    dependency_cache: Optional[Dict[Hashable, Any]] = None,
) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    dependency_cache = {} if dependency_cache is None else dependency_cache
    namespace = {} if namespace is None else namespace

    if dependent.var_namespace is not None:
        namespace.update(dependent.var_namespace())
    sub_dependent: Dependent
    for sub_dependent in dependent.dependencies:
        sub_values: Dict[str, Any] = {}
        sub_values = await solve_dependencies(
            dependent=sub_dependent,
            namespace=namespace,
            dependency_cache=dependency_cache,
            stack=stack,
        )

        args, kwargs = apply_parameter(sub_dependent, sub_values, namespace)

        cache_key = sub_dependent.make_key(sub_dependent, args, kwargs)
        if sub_dependent.use_cache and cache_key in dependency_cache:
            solved = dependency_cache[cache_key]
        else:
            solved = await apply(sub_dependent.call, args, kwargs, stack)
            if sub_dependent.use_cache:
                dependency_cache[cache_key] = solved

        if sub_dependent.name is not None:
            values[sub_dependent.name] = solved
            namespace[sub_dependent.name] = solved

    return values


async def run_dependent(
    dependent: Dependent[R],
    stack: Optional[AsyncExitStack] = None,
    **namespace: Any,
) -> R:
    assert dependent.name is None
    dependent.name = "result"
    wrap: Dependent = Dependent(dict, dependencies=[dependent])
    if stack is None:
        async with AsyncExitStack() as stack:
            solved = await solve_dependencies(
                dependent=wrap, stack=stack, namespace=namespace
            )
    else:
        solved = await solve_dependencies(
            dependent=wrap, stack=stack, namespace=namespace
        )

    return cast(R, solved.get("result"))  # pyright: ignore[reportUnboundVariable]


async def solve_dependent(
    call: Union[DependentCall[R], Dependent[R]],
    dependencies: Optional[List[Dependent]] = None,
    stack: Optional[AsyncExitStack] = None,
    var_namespace: Optional[Callable[..., Dict[str, Any]]] = None,
    **namespace: Any,
) -> R:
    dependent = get_dependent(call=call)
    if var_namespace is not None:
        dependent.var_namespace = var_namespace
    dependencies = dependencies if dependencies is not None else []
    dependent.dependencies = dependencies + (dependent.dependencies or [])

    return await run_dependent(dependent=dependent, stack=stack, **namespace)


def decorator(
    func: Callable[P, R],
    *,
    dependencies: Optional[List[Dependent]] = None,
    stack: Optional[AsyncExitStack] = None,
) -> Callable[..., Coroutine[None, None, R]]:
    async def wrapper(**kwargs: Any) -> R:
        return await solve_dependent(
            func, dependencies=dependencies, stack=stack, var_namespace=None, **kwargs
        )

    return wrapper


def builder(
    func: Optional[Callable[P, R]] = None,
    *,
    dependencies: Optional[List[Dependent]] = None,
    stack: Optional[AsyncExitStack] = None,
):
    if func is None:
        return functools.partial(decorator, dependencies=dependencies, stack=stack)
    return decorator(func, dependencies=dependencies, stack=stack)
