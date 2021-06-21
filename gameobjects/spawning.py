#!/usr/bin/env python
from __future__ import annotations

import PIL

from typing import Any, Dict, List, Sequence

from arcade import load_texture
from arcade.arcade_types import Point

from buildings.buildings import Building
from map.map import map_grid_to_position
from players_and_factions.player import Player
from units.units import Unit, Vehicle, Tank, Soldier
from utils.classes import Singleton
from utils.enums import UnitWeight, Robustness
from utils.functions import get_path_to_file, decolorised_name

from utils.logging import log
from .gameobject import GameObject, TerrainObject


class GameObjectsSpawner(Singleton):
    game = None  # assigned by the Game instance automatically

    def __init__(self):
        """
        :param configs: Dict -- data read from the CSV files in configs dir.
        """
        self.pathfinder = self.game.pathfinder
        self.configs: Dict[str, Dict[str, Dict[str, Any]]] = self.game.configs
        log(f'GameObjectsSpawner was initialized successfully...', console=True)

    def spawn(self, name: str, player: Player, position: Point, *args, **kwargs):
        if player is None:
            return self._spawn_terrain_object(name, position, *args, **kwargs)
        elif name in self.configs['buildings']:
            return self._spawn_building(name, player, position, **kwargs)
        elif name in self.configs['units']:
            return self._spawn_unit(name, player, position, **kwargs)

    def spawn_group(self,
                    names: Sequence[str],
                    player: Player,
                    position: Point, **kwargs) -> List[GameObject]:
        positions = self.pathfinder.get_group_of_waypoints(*position, len(names))
        spawned = []
        for i, name in enumerate(names):
            position = map_grid_to_position(positions[i])
            spawned.append(self.spawn(name, player, position))
        return spawned

    def _spawn_building(self, name: str, player, position, **kwargs) -> Building:
        # since player can pick various Colors we need to 'colorize" name of
        # the textures spritesheet used for his units and buildings. But for
        # the configuration of his objects we still use 'raw' name:
        category = 'buildings'
        uid = kwargs['id'] if 'id' in kwargs else None
        kwargs = self.get_entity_configs(category, name)
        return Building(name, player, position, id=uid, **kwargs)

    def _spawn_unit(self, name: str, player, position, **kwargs) -> Unit:
        category = 'units'
        class_name = eval(self.configs[category][name]['class'])
        uid = kwargs['id'] if 'id' in kwargs else None
        unit = class_name(name, player, UnitWeight.LIGHT, position, id=uid)
        return self._configure_spawned_attributes(category, name, unit)

    def get_entity_configs(self, category, name) -> Dict:
        config_data = self.configs[category][name]
        return {
            key: value for (key, value) in config_data.items() if
            value != name and 'class' not in key
        }

    def _configure_spawned_attributes(self, category, name, spawned):
        config_data = self.configs[category][name]  # 'raw' not colorized name
        for i, (key, value) in enumerate(config_data.items()):
            if i < 8 and value != name and 'class' not in key:
                setattr(spawned, key, value)
        return spawned

    def _spawn_terrain_object(self, name, position, *args, **kwagrs) -> GameObject:
        if 'wreck' in name or 'corpse' in name:
            texture_index = args[0]
            return self._spawn_wreck_or_body(name, position, texture_index)
        return GameObject(name, position=position)

    @staticmethod
    def _spawn_wreck_or_body(name, position, texture_index) -> GameObject:
        wreck = TerrainObject(name, Robustness.INDESTRUCTIBLE, position)
        texture_name = get_path_to_file(name)
        width, height = PIL.Image.open(texture_name).size
        try:  # for tanks with turrets
            i, j = texture_index  # Tuple
            wreck.texture = load_texture(texture_name, j * (width // 8),
                                         i * (height // 8), width // 8,
                                         height // 8)
        except TypeError:
            wreck.texture = load_texture(texture_name,
                                         texture_index * (width // 8),
                                         0, width // 8, height)
        return wreck
