#!/usr/bin/env python
from __future__ import annotations

import PIL

from typing import Any, Dict, List, Sequence

from arcade import load_texture, Texture
from arcade.arcade_types import Point

from buildings.buildings import Building
from map.map import map_grid_to_position
from players_and_factions.player import Player
from units.units import Unit, Soldier, Tank
from utils.classes import Singleton
from utils.functions import get_path_to_file

from utils.game_logging import log
from gameobjects.constants import BUILDINGS, UNITS, CLASS, CORPSE, WRECK, TREE
from gameobjects.gameobject import GameObject, Wreck, Tree


class GameObjectsSpawner(Singleton):
    game = None  # assigned by the Game instance automatically

    def __init__(self):
        self.pathfinder = self.game.pathfinder
        self.configs: Dict[str, Dict[str, Dict[str, Any]]] = self.game.configs
        log(f'GameObjectsSpawner was initialized successfully...', console=True)

    def spawn_group(self,
                    names: Sequence[str],
                    player: Player,
                    position: Point,
                    **kwargs) -> List[GameObject]:
        positions = self.pathfinder.get_group_of_waypoints(*position, len(names))
        spawned = []
        for i, name in enumerate(names):
            position = map_grid_to_position(positions[i])
            spawned.append(self.spawn(name, player, position, **kwargs))
        return spawned

    def spawn(self, name: str, player: Player, position: Point, *args,
              **kwargs):
        if player is None:
            return self._spawn_terrain_object(name, position, *args, **kwargs)
        elif name in self.configs[BUILDINGS]:
            return self._spawn_building(name, player, position, **kwargs)
        elif name in self.configs[UNITS]:
            return self._spawn_unit(name, player, position, **kwargs)

    def _spawn_building(self, name: str, player, position, **kwargs) -> Building:
        # in case of Building we need to provide special **kwargs to the
        # __init__ which values are retrieved from configs, these params are
        # flags telling a Building if it is a UnitsProducer, ResourceExtractor,
        # ResearchFacility etc.
        kwargs.update(
            {k: v for (k, v) in self.configs[BUILDINGS][name].items() if
             k in ('produced_units', 'produced_resource', 'research_facility')}
        )
        return Building(name, player, position, **kwargs)

    def _spawn_unit(self, name: str, player, position, **kwargs) -> Unit:
        category = UNITS
        class_name = eval(self.configs[category][name][CLASS])
        unit = class_name(name, player, 1, position, **kwargs)
        return self._get_attributes_from_configs_file(category, name, unit)

    def _get_attributes_from_configs_file(self, category, name, spawned):
        config_data = self.configs[category][name]  # 'raw' not colorized name
        for i, (key, value) in enumerate(config_data.items()):
            if i < 8 and value != name and 'class' not in key:
                setattr(spawned, key, value)
        return spawned

    def _spawn_terrain_object(self, name, position, *args, **kwargs) -> GameObject:
        if WRECK in name or CORPSE in name:
            texture_index = args[0]
            return self._spawn_wreck_or_body(name, position, texture_index)
        elif TREE in name:
            return Tree(name, 4, position)
        return GameObject(name, position=position)

    def _spawn_wreck_or_body(self, name, position, texture_index) -> Wreck:
        wreck = Wreck(name, 0 if CORPSE in name else 1, position)
        wreck.texture = self.get_proper_wreck_texture(name, texture_index)
        return wreck

    @staticmethod
    def get_proper_wreck_texture(name, texture_index) -> Texture:
        texture_name = get_path_to_file(name)
        width, height = PIL.Image.open(texture_name).size
        try:  # for tanks with turrets
            i, j = texture_index  # Tuple
            texture = load_texture(texture_name,
                                   j * (width // 8),
                                   i * (height // 8), width // 8,
                                   height // 8)
        except TypeError:
            texture = load_texture(texture_name,
                                   texture_index * (width // 8),
                                   0, width // 8, height)
        return texture
