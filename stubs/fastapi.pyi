"""Type stubs for FastAPI to improve type checking.

This stub file provides better type information for FastAPI decorators
and reduces Any type warnings in mypy.
"""

from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("_T")
# TypeVar for decorated callables - using object instead of Any to avoid explicit Any errors
# The ellipsis in Callable[..., object] is standard Python syntax for variadic callables
_DecoratedCallable = TypeVar("_DecoratedCallable")

class FastAPI:
    """FastAPI application stub"""
    def __init__(
        self,
        *,
        title: str | None = None,
        version: str | None = None,
        openapi_url: str | None = "/openapi.json",
        docs_url: str | None = "/docs",
        redoc_url: str | None = "/redoc",
        **kwargs: object,
    ) -> None: ...
    def get(
        self,
        path: str,
        *,
        response_model: type[object] | None = None,
        status_code: int = 200,
        tags: list[str] | None = None,
        dependencies: object = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, object]] | None = None,
        deprecated: bool | None = None,
        operation_id: str | None = None,
        response_model_include: object = None,
        response_model_exclude: object = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: str | None = None,
        callbacks: object = None,
        openapi_extra: dict[str, object] | None = None,
        generate_unique_id_function: Callable[[object], str] | None = None,
    ) -> Callable[[_DecoratedCallable], _DecoratedCallable]: ...
    def post(
        self,
        path: str,
        *,
        response_model: type[object] | None = None,
        status_code: int = 200,
        tags: list[str] | None = None,
        dependencies: object = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, object]] | None = None,
        deprecated: bool | None = None,
        operation_id: str | None = None,
        response_model_include: object = None,
        response_model_exclude: object = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: str | None = None,
        callbacks: object = None,
        openapi_extra: dict[str, object] | None = None,
        generate_unique_id_function: Callable[[object], str] | None = None,
    ) -> Callable[[_DecoratedCallable], _DecoratedCallable]: ...
    def put(
        self,
        path: str,
        *,
        response_model: type[object] | None = None,
        status_code: int = 200,
        tags: list[str] | None = None,
        dependencies: object = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, object]] | None = None,
        deprecated: bool | None = None,
        operation_id: str | None = None,
        response_model_include: object = None,
        response_model_exclude: object = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: str | None = None,
        callbacks: object = None,
        openapi_extra: dict[str, object] | None = None,
        generate_unique_id_function: Callable[[object], str] | None = None,
    ) -> Callable[[_DecoratedCallable], _DecoratedCallable]: ...
    def delete(
        self,
        path: str,
        *,
        response_model: type[object] | None = None,
        status_code: int = 200,
        tags: list[str] | None = None,
        dependencies: object = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, object]] | None = None,
        deprecated: bool | None = None,
        operation_id: str | None = None,
        response_model_include: object = None,
        response_model_exclude: object = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: str | None = None,
        callbacks: object = None,
        openapi_extra: dict[str, object] | None = None,
        generate_unique_id_function: Callable[[object], str] | None = None,
    ) -> Callable[[_DecoratedCallable], _DecoratedCallable]: ...
    def add_middleware(
        self,
        middleware_class: type[object],
        **kwargs: object,
    ) -> None: ...

class HTTPException(Exception):
    """HTTP Exception stub"""
    def __init__(
        self,
        status_code: int,
        detail: object = None,
        headers: dict[str, str] | None = None,
    ) -> None: ...

class CORSMiddleware:
    """CORS Middleware stub"""

    pass
