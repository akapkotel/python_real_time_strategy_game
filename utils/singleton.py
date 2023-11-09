#!/usr/bin/env python3
from weakref import WeakValueDictionary
import threading


class SingletonMeta(type):
    _instances = WeakValueDictionary()
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            try:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
            except Exception as e:
                # handle exception here
                print(f"Error creating instance: {e}")
            return cls._instances[cls]

    @classmethod
    def delete_instance(cls):
        try:
            del cls._instances[cls]
        except KeyError:
            pass
