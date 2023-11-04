#!/usr/bin/env python

import logging
from typing import Union


console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(
    'resources/logging/logfile.txt',
    'w'
)


file_logger = logging.getLogger('file_handler')
file_logger.addHandler(file_handler)
file_logger.setLevel(logging.INFO)

console_logger = logging.getLogger('console_handler')
console_logger.addHandler(console_handler)
console_logger.setLevel(logging.INFO)


log_formatter = logging.Formatter(
    '%(levelname)s: %(asctime)s %(message)s',
    '%m/%d/%Y %I:%M:%S %p'
)
for logger in (console_logger, file_logger):
    for handler in logger.handlers:
        handler.setFormatter(log_formatter)


def log_here(logged_message: str, console: Union[int, bool] = False):
    full_file_path, line_number, function, stack = logger.findCaller()
    filename = full_file_path.split('\\')[-1]
    message = f' | {filename, line_number, function, stack} | {logged_message}'
    file_logger.info(message, exc_info=True)
    if console:
        console_logger.info(message, exc_info=True)


def log_this_call(console=False):
    """Decorator for logging function calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            log_here(f'func: {func.__name__} args: {args}, kwargs: {kwargs}', console)
            return func(*args, **kwargs)
        return wrapper
    return decorator


