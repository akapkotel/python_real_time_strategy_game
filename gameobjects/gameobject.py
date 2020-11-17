#!/usr/bin/env python
from __future__ import annotations

from typing import Optional

from arcade import AnimatedTimeBasedSprite
from arcade.arcade_types import Point

from utils.improved_spritelists import DividedSpriteList
from utils.enums import Robustness, UnitWeight
from utils.observers import OwnedObject
from utils.functions import get_path_to_file, log
from game import Game


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
        print(filename)
        super().__init__(filename, center_x=x, center_y=y)
        OwnedObject.__init__(self, owners=True)
        self.object_name = object_name

        GameObject.total_objects_count += 1
        self.id = count = GameObject.total_objects_count

        self._robustness = robustness  # used to determine if object makes a
        # tile not-walkable or can be destroyed by vehicle entering the MapTile

        self._visible = True

        self.divided_spritelist: Optional[DividedSpriteList] = None

        log(f'Spawned {self} at {self.position}, total objects: {count}', True)

    def __repr__(self) -> str:
        return f'GameObject: {self.object_name} id: {self.id}'

    @property
    def visible(self):
        return self._visible

    def destructible(self, weight: UnitWeight = 0) -> bool:
        return weight > self._robustness

    def on_update(self, delta_time: float = 1/60):
        self.center_x += self.change_x
        self.center_y += self.change_y
        if self.frames:
            self.update_animation(delta_time)

    def update_animation(self, delta_time: float = 1 / 60):
        super().update_animation(delta_time)

    def start_drawing(self):
        self.divided_spritelist.start_drawing(self)

    def stop_drawing(self):
        self.divided_spritelist.stop_drawing(self)

    def start_updating(self):
        self.divided_spritelist.start_updating(self)

    def stop_updating(self):
        self.divided_spritelist.stop_updating(self)

    def kill(self):
        self.sprite_lists.clear()
        self.unregister_from_all_owners()
        self.divided_spritelist.remove(self)
        super().kill()


class TerrainObject(GameObject):

    def __init__(self, filename: str):
        super().__init__(filename)
        grid = self.game.map.position_to_grid(*self.position)
        self.game.map.nodes[grid].obstacle_id = self.id
