#!/usr/bin/env python
from __future__ import annotations

import PIL

from typing import Any, Dict, List, Sequence, Tuple

from arcade import load_texture
from arcade.arcade_types import Point

from buildings.buildings import Building
from players_and_factions.player import Player
from units.units import Unit, Vehicle, Tank
from utils.classes import Singleton
from utils.enums import UnitWeight, Robustness
from utils.functions import (
    add_player_color_to_name, get_path_to_file, to_texture_name,
    decolorized_name
)
from .gameobject import GameObject, TerrainObject


class ObjectsFactory(Singleton):

    def __init__(self,
                 pathfinder,
                 configs: Dict[str, Dict[str, Dict[str, Any]]]):
        """
        :param configs: Dict -- data read from the CSV files in configs dir.
        """
        self.pathfinder = pathfinder
        self.configs = configs

    def spawn(self, name: str, player: Player, position: Point, *args, **kwargs):
        name = to_texture_name(decolorized_name(name))
        if player is None:
            obj = self._spawn_terrain_object(name, position, *args, **kwargs)
        if name in self.configs['buildings']:
            obj = self._spawn_building(name, player, position, **kwargs)
        elif name in self.configs['units']:
            obj = self._spawn_unit(name, player, position, **kwargs)
        if 'id' in kwargs:
            obj.id = kwargs['id']
        return obj

    def spawn_group(self,
                    names: Sequence[str],
                    player: Player,
                    position: Point, **kwargs) -> List[GameObject]:
        positions = self.pathfinder.get_group_of_waypoints(*position, len(names))
        spawned = []
        for i, name in enumerate(names):
            position = self.pathfinder.map.grid_to_position(positions[i])
            spawned.append(self.spawn(name, player, position))
        return spawned

    def _spawn_building(self, name: str, player, position, **kwargs) -> Building:
        # since player can pick various Colors we need to 'colorize" name of
        # the textures spritesheet used for his units and buildings. But for
        # the configuration of his objects we still use 'raw' name:
        colorized_name = add_player_color_to_name(name, player.color)
        building = Building(colorized_name, player, position, **kwargs)
        category = 'buildings'
        return self._configure_spawned_attributes(category, name, building)

    def _spawn_unit(self, name: str, player, position, **kwargs) -> Unit:
        category = 'units'
        class_name = eval(self.configs[category][name]['class'])
        colorized_name = add_player_color_to_name(name, player.color)
        if 'id' in kwargs:
            unit = class_name(colorized_name, player, UnitWeight.LIGHT, position, kwargs['id'])
        else:
            unit = class_name(colorized_name, player, UnitWeight.LIGHT, position)
        return self._configure_spawned_attributes(category, name, unit)

    def _configure_spawned_attributes(self, category, name, spawned):
        config_data = self.configs[category][name]  # 'raw' not colorized name
        for key, value in config_data.items():
            if value != name and 'class' not in key:
                setattr(spawned, key, value)
        return spawned

    def _spawn_terrain_object(self, name, position, *args, **kwagrs) -> GameObject:
        if 'wreck' in name:
            texture_index = args[0]
            return self._spawn_wreck(name, position, texture_index)
        category = 'terrain'
        return GameObject(name, position=position)

    def _spawn_wreck(self, name, position, texture_index) -> GameObject:
        wreck = TerrainObject(name, Robustness.INDESTRUCTIBLE, position)
        texture_name = get_path_to_file(name)
        width, height = PIL.Image.open(texture_name).size
        if isinstance(texture_index, Tuple):
            i, j = texture_index
            wreck.texture = load_texture(texture_name, j * (width // 8),
                                         i * (height // 8), width // 8,
                                         height // 8)
        else:
            wreck.texture = load_texture(texture_name,
                                         texture_index * (width // 8),
                                         0, width // 8, height)
        return wreck

    @staticmethod
    def despawn(game_object: GameObject):
        try:
            game_object.kill()
        except AttributeError:
            pass
