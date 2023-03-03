#!/usr/bin/env python
from time import perf_counter

from utils.game_logging import log


def timer(level=0, global_profiling_level=0, forced=False):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if forced or level <= global_profiling_level:
                try:
                    start_time = perf_counter()
                    result = func(*args, **kwargs)
                    execution_time = perf_counter() - start_time
                    log(f"{func.__name__} executed in {execution_time:.4f} secsonds.", console=True)
                    return result
                except Exception as e:
                    log(str(e), console=True)
                    return e
            return func(*args, **kwargs)
        return wrapper
    return decorator
