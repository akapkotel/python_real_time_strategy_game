#!/usr/bin/env python
from __future__ import annotations

from typing import Dict, Any

from gameobjects.gameobject import GameObject
from utils.enums import UnitWeight
from utils.classes import Singleton


class ObjectsSpawner(Singleton):

    def __init__(self, configs: Dict[Dict[Dict[str, Any]]]):
        self.configs = configs

    def spawn(self, name: str, classname: type(GameObject), player, x, y) -> GameObject:
        spawned = classname(name, player, UnitWeight.LIGHT, (x, y))
        category = 'buildings' if spawned.is_building else 'units'

        config_data = self.configs[category][name]
        for key, value in config_data.items():
            if value != name and 'class' not in key:
                setattr(spawned, key, value)
        return spawned
