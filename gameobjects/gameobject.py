#!/usr/bin/env python
from __future__ import annotations

from functools import lru_cache, cached_property
from typing import Optional, Dict, List

from arcade import AnimatedTimeBasedSprite
from arcade.arcade_types import Point

from utils.classes import Observed, Observer
from utils.data_types import GridPosition
from utils.functions import (
    get_path_to_file, decolorised_name, add_extension
)
from utils.logging import log
from utils.improved_spritelists import LayeredSpriteList
from utils.scheduling import EventsCreator, ScheduledEvent


class GameObject(AnimatedTimeBasedSprite, EventsCreator, Observed):
    """
    GameObject represents all in-game objects, like units, buildings,
    terrain props, trees etc.
    """
    game = None
    total_objects_count = 0

    def __init__(self, texture_name: str, durability: int = 0,
                 position: Point = (0, 0), id: Optional[int] = None,
                 observers: Optional[List[Observer]] = None):
        # raw name of the object without texture extension and Player color
        # used to query game.configs and as a basename to build other names
        self.object_name = decolorised_name(texture_name)
        # name with texture extension added used to find ant load texture
        self.full_name = add_extension(texture_name)
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

        self._durability = durability  # used to determine if object makes a
        # tile not-walkable or can be destroyed by vehicle entering the MapTile

        self.is_updated = True
        self.is_rendered = True

        self.layered_spritelist: Optional[LayeredSpriteList] = None

    def __repr__(self) -> str:
        return f'GameObject: {self.object_name} id: {self.id}'

    @property
    def timer(self):
        return self.game.timer

    @cached_property
    def text_hint(self) -> str:
        """
        Format and return string displayed when mouse cursor points at this
        object for time greater than Settings.hints_delay.
        """
        return self.object_name.title().replace('_', ' ')

    @property
    def on_screen(self) -> bool:
        l, r, b, t = self.game.viewport
        return l < self.right and r > self.left and b < self.top and t > self.bottom

    def destructible(self, weight: int = 0) -> bool:
        return weight > self._durability

    def on_update(self, delta_time: float = 1 / 60):
        self.update_visibility()
        self.center_x += self.change_x
        self.center_y += self.change_y
        if self.frames:
            self.update_animation(delta_time)

    def update_visibility(self):
        if self.should_be_rendered:
            if not self.is_rendered:
                self.start_drawing()
        elif self.is_rendered:
            self.stop_drawing()

    @property
    def should_be_rendered(self) -> bool:
        return self.on_screen

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
        log(f'Destroying GameObject: {self}', True)
        try:
            self.layered_spritelist.remove(self)
        except (AttributeError, ValueError):
            pass
        finally:
            self.detach_observers()
            super().kill()

    def save(self) -> Dict:
        return {
            'id': self.id,
            'object_name': self.object_name,
            'position': self._position,  # (self.center_x, self.center_y)
        }


class TerrainObject(GameObject):

    def __init__(self, filename: str, durability: int, position: Point):
        GameObject.__init__(self, filename, durability, position)
        self.map_node = self.game.map.position_to_node(*self.position)
        if durability:
            self.map_node.static_gameobject = self
        self.attach(observer=self.game)

    def draw(self):
        # TerrainObjects are not updated, so we need check here if to render
        if self.on_screen:
            super().draw()

    def kill(self):
        self.map_node.static_gameobject = None
        super().kill()


class Tree(TerrainObject):

    def __init__(self, filename: str, durability: int, position: Point):
        super().__init__(filename, durability, position)
        self.map_node.tree = self

    def kill(self):
        self.map_node.tree = None
        super().kill()


class Wreck(TerrainObject):

    def __init__(self, filename: str, durability: int, position: Point):
        super().__init__(filename, durability, position)
        lifetime = self.game.settings.remove_wrecks_after
        self.schedule_event(ScheduledEvent(self, lifetime, self.kill))


class PlaceableGameobject:
    """
    Used be ScenarioEditor and MouseCursor classes to attach a GameObject to
    the cursor allowing user to move it around the map and spawn it wherever he
    wants with a mouse-click.
    """

    def __init__(self, gameobject_name: str):
        self.game = GameObject.game
        self.gameobject_name = gameobject_name

    def emplace(self, position: GridPosition):
        self.game.spawn(self.gameobject_name, )
        raise NotImplementedError
