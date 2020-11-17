#!/usr/bin/env python
from __future__ import annotations

from typing import Dict, Any

from arcade.arcade_types import Point

from players_and_factions.player import Player
from .gameobject import GameObject
from buildings.buildings import Building
from units.units import Unit, Vehicle
from utils.enums import UnitWeight
from utils.classes import Singleton


class ObjectsFactory(Singleton):

    def __init__(self, configs: Dict[str, Dict[str, Dict[str, Any]]]):
        """
        :param configs: Dict -- data read from the CSV files in configs dir.
        """
        self.configs = configs

    def spawn(self, name: str, player: Player, position: Point, **kwargs):
        if kwargs:
            return self._spawn_building(name, player, position, **kwargs)
        elif name in self.configs['units']:
            return self._spawn_unit(name, player, position)
        return self._spawn_terrain_object(name, position)

    def _spawn_building(self, name: str, player, position, **kwargs) -> Building:
        print(kwargs)
        building = Building(name, player, position, **kwargs)
        category = 'buildings'
        return self._configure_spawned_attributes(category, name, building)

    def _spawn_unit(self, name: str, player, position) -> Unit:
        category = 'units'
        classname = eval(self.configs[category][name]['class'])
        unit = classname(name, player, UnitWeight.LIGHT, position)
        return self._configure_spawned_attributes(category, name, unit)

    def _configure_spawned_attributes(self, category, name, spawned):
        config_data = self.configs[category][name]
        for key, value in config_data.items():
            if value != name and 'class' not in key:
                setattr(spawned, key, value)
        return spawned

    def _spawn_terrain_object(self, name, position) -> GameObject:
        category = 'terrain'
        return GameObject(name, position=position)
