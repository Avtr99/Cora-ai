"""
Reusable design patterns for the RAG system.

Provides:
- Singleton decorator for thread-safe singleton instances
- API error handling decorator for FastAPI routes
- Health check wrapper for component monitoring
"""
import threading
import time
from functools import wraps
from typing import TypeVar, Type, Callable, Any, Optional, Dict
from loguru import logger

T = TypeVar('T')


class SingletonMeta(type):
    """
    Thread-safe Singleton metaclass.
    
    Usage:
        class MyClass(metaclass=SingletonMeta):
            def __init__(self):
                # initialization code
                pass
    """
    _instances: Dict[Type, Any] = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]
    
    @classmethod
    def reset_instance(mcs, cls: Type) -> None:
        """Reset a singleton instance (useful for testing)."""
        with mcs._lock:
            if cls in mcs._instances:
                del mcs._instances[cls]


def singleton(cls: Type[T]) -> Type[T]:
    """
    Thread-safe singleton decorator.
    
    Usage:
        @singleton
        class MyClass:
            def __init__(self):
                # initialization code
                pass
        
        # Get instance
        instance = MyClass.get_instance()
    """
    cls._instance: Optional[T] = None
    cls._lock = threading.Lock()
    
    @classmethod
    def get_instance(klass) -> T:
        """Get or create the singleton instance."""
        if klass._instance is None:
            with klass._lock:
                if klass._instance is None:
                    klass._instance = object.__new__(klass)
                    if hasattr(klass._instance, '_initialize'):
                        klass._instance._initialize()
                    elif hasattr(klass, '__init__'):
                        klass._instance.__init__()
        return klass._instance
    
    @classmethod
    def reset_instance(klass) -> None:
        """Reset the singleton instance (useful for testing)."""
        with klass._lock:
            klass._instance = None
    
    cls.get_instance = get_instance
    cls.reset_instance = reset_instance
    
    return cls


def handle_api_errors(
    default_status_code: int = 500,
    error_mappings: Optional[Dict[Type[Exception], int]] = None
):
    """
    Decorator for handling API route errors consistently.
    
    Wraps async route handlers with try-except and converts exceptions
    to appropriate HTTPException responses.
    
    Args:
        default_status_code: Default HTTP status code for unhandled exceptions
        error_mappings: Dict mapping exception types to status codes
        
    Usage:
        @router.get("/items/{item_id}")
        @handle_api_errors(error_mappings={ValueError: 400, KeyError: 404})
        async def get_item(item_id: str):
            # route logic
            pass
    """
    from fastapi import HTTPException
    
    mappings = error_mappings or {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                # Check for specific exception mappings
                for exc_type, status_code in mappings.items():
                    if isinstance(e, exc_type):
                        logger.warning(f"API error in {func.__name__}: {e}")
                        raise HTTPException(
                            status_code=status_code,
                            detail="Request could not be processed"
                        )
                
                # Default error handling - log full error internally, return generic message
                logger.error(f"Unhandled error in {func.__name__}: {e}", exc_info=True)
                raise HTTPException(
                    status_code=default_status_code,
                    detail="An internal error occurred"
                )
        
        return wrapper
    return decorator


async def check_component_health(
    name: str,
    check_fn: Callable[[], Any],
    details_fn: Optional[Callable[[Any], Dict[str, Any]]] = None
):
    """
    Generic health check wrapper for system components.
    
    Executes a health check function with timing and error handling,
    returning a standardized ComponentHealth result.
    
    Args:
        name: Component name for the health check result
        check_fn: Function to execute for the health check (can be sync or async)
        details_fn: Optional function to extract details from check result
        
    Returns:
        ComponentHealth object with status, latency, and optional details
        
    Usage:
        health = await check_component_health(
            name="database",
            check_fn=lambda: db.ping(),
            details_fn=lambda result: {"version": result.version}
        )
    """
    import asyncio
    from ..api.health import ComponentHealth, HealthStatus
    
    start = time.perf_counter()
    
    try:
        # Execute check function (handle both sync and async)
        if asyncio.iscoroutinefunction(check_fn):
            result = await check_fn()
        else:
            result = check_fn()
        
        latency = (time.perf_counter() - start) * 1000
        
        # Extract details if function provided
        details = {}
        if details_fn and result is not None:
            try:
                details = details_fn(result)
            except Exception as details_err:
                logger.debug(f"Failed to extract health check details for {name}: {details_err}")
        
        return ComponentHealth(
            name=name,
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            details=details
        )
        
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        logger.error(f"{name} health check failed: {e}", exc_info=True)
        
        return ComponentHealth(
            name=name,
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            message="Health check failed"
        )
