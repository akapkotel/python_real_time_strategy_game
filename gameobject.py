#!/usr/bin/env python
from __future__ import annotations

from arcade import (
    Sprite, AnimatedTimeBasedSprite, SpriteList, get_sprites_at_point
)
from arcade.arcade_types import Point

from typing import Any, Optional, List, Set

from data_containers import DividedSpriteList
from enums import UnitWeight, Robustness
from functions import get_object_name, filter_sequence
from observers import OwnedObject


def get_gameobjects_at_position(position: Point,
                                objects_list: List[Any]) -> Set[GameObject]:
    gameobjects: Set[GameObject] = set()
    for spritelist in reversed(filter_sequence(objects_list, SpriteList)):
        gameobjects.update(
            s for s in get_sprites_at_point(position, spritelist) if
            isinstance(s, GameObject)
        )
    return gameobjects


class GameObject(AnimatedTimeBasedSprite, OwnedObject):
    """
    Inherit from this class instead of arcade.Sprite to implement some useful
    methods.
    """
    total_objects_count = 0

    def __init__(self,
                 filename: str,
                 robustness: Robustness = 0,
                 position: Point = (0, 0)):
        x, y = position
        Sprite.__init__(self, filename, center_x=x, center_y=y)
        self.object_name = get_object_name(filename)

        GameObject.total_objects_count += 1
        self.id = GameObject.total_objects_count

        self._robustness = robustness  # used to determine if object makes a
        # tile not-walkable or can be destroyed by vehicle entering the MapTile

        self._visible = True

        self.divided_spritelist: Optional[DividedSpriteList] = None

    def __repr__(self) -> str:
        return f'GameObject: {self.object_name} id: {self.id}'

    @property
    def visible(self):
        return self._visible

    def destructible(self, weight: UnitWeight = 0) -> bool:
        return weight > self._robustness

    def update_animation(self, delta_time: float = 1 / 60):
        super().update_animation(delta_time)

    def kill(self):
        self.divided_spritelist.remove(self)
        super().kill()
