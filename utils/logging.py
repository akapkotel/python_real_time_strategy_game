#!/usr/bin/env python

import logging
from time import perf_counter
from typing import Union


logging.basicConfig(
    filename='resources/logging/logfile.txt',
    filemode='w',
    level=logging.INFO,
    format='%(levelname)s: %(asctime)s %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p'
)


def log(logged_message: str, console: Union[int, bool] = False):
    logging.info(logged_message)
    if console:
        print(logged_message)


def logger(console=False):
    def decorator(func):
        def wrapper(*args, **kwargs):
            log(f'Called function: {func.__name__}, args: {args}, kwargs: {kwargs}', console)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def timer(level=0, global_profiling_level=0, forced=False):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if forced or level < global_profiling_level:
                try:
                    start_time = perf_counter()
                    result = func(*args, **kwargs)
                    execution_time = perf_counter() - start_time

                    fps = 1 / execution_time
                    log(f"{func.__name__} finished in {execution_time:.4f} secs. FPS:{fps}", console=True)
                    return result
                except Exception as e:
                    log(str(e), console=True)
                    return e
            return func(*args, **kwargs)
        return wrapper
    return decorator
