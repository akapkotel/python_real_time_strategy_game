#!/usr/bin/env python

import logging
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


