"""Type stubs for FastAPI to improve type checking.

This stub file provides better type information for FastAPI decorators
and reduces Any type warnings in mypy.
"""

from typing import Any, Callable, TypeVar, overload
from collections.abc import Awaitable

_T = TypeVar("_T")
_DecoratedCallable = TypeVar("_DecoratedCallable", bound=Callable[..., Any])

class FastAPI:
    """FastAPI application stub"""
    def get(
        self, 
        path: str,
        *,
        response_model: type[Any] | None = None,
        status_code: int = 200,
        tags: list[str] | None = None,
        dependencies: Any = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, Any]] | None = None,
        deprecated: bool | None = None,
        operation_id: str | None = None,
        response_model_include: Any = None,
        response_model_exclude: Any = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: str | None = None,
        callbacks: Any = None,
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Callable[[Any], str] | None = None,
    ) -> Callable[[_DecoratedCallable], _DecoratedCallable]: ...
    
    def post(
        self,
        path: str,
        *,
        response_model: type[Any] | None = None,
        status_code: int = 200,
        tags: list[str] | None = None,
        dependencies: Any = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, Any]] | None = None,
        deprecated: bool | None = None,
        operation_id: str | None = None,
        response_model_include: Any = None,
        response_model_exclude: Any = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: str | None = None,
        callbacks: Any = None,
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Callable[[Any], str] | None = None,
    ) -> Callable[[_DecoratedCallable], _DecoratedCallable]: ...
    
    def put(
        self,
        path: str,
        *,
        response_model: type[Any] | None = None,
        status_code: int = 200,
        tags: list[str] | None = None,
        dependencies: Any = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, Any]] | None = None,
        deprecated: bool | None = None,
        operation_id: str | None = None,
        response_model_include: Any = None,
        response_model_exclude: Any = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: str | None = None,
        callbacks: Any = None,
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Callable[[Any], str] | None = None,
    ) -> Callable[[_DecoratedCallable], _DecoratedCallable]: ...
    
    def delete(
        self,
        path: str,
        *,
        response_model: type[Any] | None = None,
        status_code: int = 200,
        tags: list[str] | None = None,
        dependencies: Any = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = "Successful Response",
        responses: dict[int | str, dict[str, Any]] | None = None,
        deprecated: bool | None = None,
        operation_id: str | None = None,
        response_model_include: Any = None,
        response_model_exclude: Any = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        include_in_schema: bool = True,
        name: str | None = None,
        callbacks: Any = None,
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Callable[[Any], str] | None = None,
    ) -> Callable[[_DecoratedCallable], _DecoratedCallable]: ...
    
    def add_middleware(
        self,
        middleware_class: type[Any],
        **kwargs: Any,
    ) -> None: ...

class HTTPException(Exception):
    """HTTP Exception stub"""
    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None: ...

class CORSMiddleware:
    """CORS Middleware stub"""
    pass

