#!/usr/bin/env python
from __future__ import annotations

from typing import Optional, Dict, List

from arcade import AnimatedTimeBasedSprite
from arcade.arcade_types import Point

from utils.classes import Observed, Observer
from utils.data_types import GridPosition
from utils.enums import Robustness, UnitWeight
from utils.functions import (
    get_path_to_file, decolorised_name, name_with_extension
)
from utils.logging import log
from utils.improved_spritelists import SelectiveSpriteList
from utils.scheduling import EventsCreator
from user_interface.user_interface import OwnedObject


class GameObject(AnimatedTimeBasedSprite, EventsCreator, Observed):
    """
    GameObject represents all in-game objects, like units, buildings,
    terrain props, trees etc.
    """
    game = None
    total_objects_count = 0

    def __init__(self,
                 texture_name: str,
                 robustness: Robustness = 0,
                 position: Point = (0, 0),
                 id: Optional[int] = None,
                 observers: Optional[List[Observer]] = None):
        # raw name of the object without texture extension and Player color
        # used to query game.configs and as a basename to build other names
        self.object_name = decolorised_name(texture_name)
        # name with texture extension added used to find ant load texture
        self.full_name = name_with_extension(texture_name)
        self.filename_with_path = get_path_to_file(self.full_name)
        x, y = position
        super().__init__(self.filename_with_path, center_x=x, center_y=y)
        Observed.__init__(self, observers)
        EventsCreator.__init__(self)

        GameObject.total_objects_count += 1
        if id is None:
            self.id = GameObject.total_objects_count
        else:
            self.id = id

        self._robustness = robustness  # used to determine if object makes a
        # tile not-walkable or can be destroyed by vehicle entering the MapTile

        self.is_updated = True
        self.is_rendered = True

        self.selective_spritelist: Optional[SelectiveSpriteList] = None

    def __repr__(self) -> str:
        return f'GameObject: {self.object_name} id: {self.id}'

    def save(self) -> Dict:
        return {
            'id': self.id,
            'object_name': self.object_name,
            'position': self._position,  # (self.center_x, self.center_y)
            'scheduled_events': self.shelve_scheduled_events()
        }

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
        self.is_rendered = True

    def stop_drawing(self):
        self.is_rendered = False

    def start_updating(self):
        self.is_updated = True

    def stop_updating(self):
        self.is_updated = False

    def on_mouse_enter(self):
        pass

    def on_mouse_exit(self):
        pass

    def kill(self):
        log(f'Destroying GameObject: {self.object_name}', True)
        try:
            self.selective_spritelist.remove(self)
        finally:
            self.detach_observers()
            super().kill()


class TerrainObject(GameObject):

    def __init__(self, filename: str, robustness: Robustness, position: Point):
        GameObject.__init__(self, filename, robustness, position)
        self.map_node = self.game.map.position_to_node(*self.position)
        self.map_node.pathable = False

    def kill(self):
        self.map_node.pathable = True
        super().kill()


class PlaceableGameobject:
    """
    Used be ScenarioEditor and MouseCursor classes to attach a GameObject to
    the cursor allowing user to move it around the map and spawn it wherever he
    wants with a mouse-click.
    """

    def __init__(self, gameobject_name: str):
        self.gameobject_name = gameobject_name

    def emplace(self, position: GridPosition):
        raise NotImplementedError
