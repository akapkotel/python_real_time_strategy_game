#!/usr/bin/env python


class Singleton:
    instances = {}

    def __new__(cls, *args, **kwargs):
        try:
            return Singleton.instances[cls]
        except KeyError:
            Singleton.instances[cls] = singleton = super().__new__(cls)
            return singleton

        # if (singleton := Singleton.instances.get(cls)) is None:
        #     instance = super().__new__(cls)
        #     Singleton.instances[cls] = instance
        #     return instance
        # else:
        #     return singleton

