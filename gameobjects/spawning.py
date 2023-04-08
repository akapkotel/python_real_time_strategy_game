#!/usr/bin/env python
from __future__ import annotations

from typing import Any, Dict

from arcade.arcade_types import Point

from buildings.buildings import Building
from players_and_factions.player import Player
from units.units import *

from utils.game_logging import log
from gameobjects.constants import (
    CLASS,
    CORPSE,
    WRECK,
    TREE,
    VEHICLE_WITH_TURRET,
    VEHICLE,
    SOLDIER,
    BUILDING,
    RESEARCH_FACILITY,
    PRODUCED_RESOURCE,
    PRODUCED_UNITS
)
from gameobjects.gameobject import GameObject, Wreck, Tree, Corpse


class GameObjectsSpawner:
    game = None  # assigned by the Game instance automatically

    def __init__(self):
        self.pathfinder = self.game.pathfinder
        self.configs: Dict[str, Dict[str, Any]] = self.game.configs
        log(f'GameObjectsSpawner was initialized successfully. Found {len(self.configs)} entities in config file.', console=True)

    def spawn(self, name: str, player: Player, position: Point, *args, **kwargs):
        if player is None:
            return self._spawn_terrain_object(name, position, *args, **kwargs)
        elif self.configs[name][CLASS] == BUILDING:
            return self._spawn_building(name, player, position, **kwargs)
        elif self.configs[name][CLASS] in (SOLDIER, VEHICLE, VEHICLE_WITH_TURRET):
            return self._spawn_unit(name, player, position, **kwargs)

    def _spawn_building(self, name: str, player, position, **kwargs) -> Building:
        kwargs.update(
            {k: v for (k, v) in self.configs[name].items() if
             k in (PRODUCED_UNITS, PRODUCED_RESOURCE, RESEARCH_FACILITY)}
        )
        return Building(name, player, position, **kwargs)

    def _spawn_unit(self, name: str, player, position, **kwargs) -> Unit:
        spawned_object_class = eval(self.configs[name][CLASS])
        unit = spawned_object_class(name, player, 1, position, **kwargs)
        return self._get_attributes_from_configs_file(name, unit)

    def _get_attributes_from_configs_file(self, name, spawned):
        config_data = self.configs[name]  # 'raw' not colorized name
        for i, (key, value) in enumerate(config_data.items()):
            if i < 8 and value != name and CLASS not in key:
                setattr(spawned, key, value)
        return spawned

    @staticmethod
    def _spawn_terrain_object(name, position, *args, **kwargs) -> GameObject:
        if WRECK in name:
            texture_index = args[0]
            return Wreck(name, 0 if CORPSE in name else 1, position, texture_index)
        if CORPSE in name:
            texture_index = args[0]
            return Corpse(name, 0 if CORPSE in name else 1, position, texture_index)
        if TREE in name:
            return Tree(name, 4, position)
        return GameObject(name, position=position)
