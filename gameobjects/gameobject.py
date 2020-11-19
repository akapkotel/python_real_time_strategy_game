#!/usr/bin/env python
from __future__ import annotations

from typing import Optional

from arcade import AnimatedTimeBasedSprite
from arcade.arcade_types import Point

from game import Game
from utils.enums import Robustness, UnitWeight
from utils.functions import get_path_to_file, log
from utils.improved_spritelists import SelectiveSpriteList
from utils.observers import OwnedObject


class GameObject(AnimatedTimeBasedSprite, OwnedObject):
    """
    GameObject represents all in-game objects, like units, buildings,
    terrain props, trees etc.
    """
    game: Optional[Game] = None
    total_objects_count = 0

    def __init__(self,
                 object_name: str,
                 robustness: Robustness = 0,
                 position: Point = (0, 0)):
        x, y = position
        filename = get_path_to_file(object_name)
        super().__init__(filename, center_x=x, center_y=y)
        OwnedObject.__init__(self, owners=True)
        self.object_name = object_name

        GameObject.total_objects_count += 1
        self.id = count = GameObject.total_objects_count

        self._robustness = robustness  # used to determine if object makes a
        # tile not-walkable or can be destroyed by vehicle entering the MapTile

        self.updated = True
        self.rendered = True

        self.selective_spritelist: Optional[SelectiveSpriteList] = None

        log(f'Spawned {self} at {self.position}, total objects: {count}')

    def __repr__(self) -> str:
        return f'GameObject: {self.object_name} id: {self.id}'

    def destructible(self, weight: UnitWeight = 0) -> bool:
        return weight > self._robustness

    def on_update(self, delta_time: float = 1 / 60):
        self.center_x += self.change_x
        self.center_y += self.change_y
        if self.frames:
            self.update_animation(delta_time)

    def update_animation(self, delta_time: float = 1 / 60):
        super().update_animation(delta_time)

    def start_drawing(self):
        self.rendered = True

    def stop_drawing(self):
        self.rendered = False

    def start_updating(self):
        self.updated = True

    def stop_updating(self):
        self.updated = False

    def kill(self):
        self.unregister_from_all_owners()
        self.selective_spritelist.remove(self)
        self.sprite_lists.clear()
        super().kill()


class TerrainObject(GameObject):

    def __init__(self, filename: str):
        super().__init__(filename)
        grid = self.game.map.position_to_grid(*self.position)
        self.game.map.nodes[grid].obstacle_id = self.id
