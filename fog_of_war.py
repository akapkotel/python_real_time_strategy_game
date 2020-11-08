#!/usr/bin/env python

from functools import lru_cache
from typing import List, Optional

from arcade import SpriteSolidColor
from numba import njit

from game import Game, SCREEN_HEIGHT, SCREEN_WIDTH
from observers import ObjectsOwner, OwnedObject
from player import PlayerEntity
from scheduling import log


class FogRectangle(SpriteSolidColor):

    def __init__(self, x: int, y: int, width: int, height: int, color):
        super().__init__(width, height, color)
        self._position = x + width // 2, y + height // 2
        self.x = x
        self.y = y

    @property
    def left_bottom(self):
        return self.x, self.y

    @property
    def right_bottom(self):
        return self.x + self.width, self.y

    @property
    def right_top(self):
        return self.x + self.width, self.y + self.height

    @property
    def left_top(self):
        return self.x, self.y + self.height


class FogOfWar(ObjectsOwner):
    game: Optional[Game] = None

    def __init__(self, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT):
        self.map_observers: List[PlayerEntity] = []

    def register(self, acquired: OwnedObject):
        acquired: PlayerEntity
        self.map_observers.append(acquired)

    def unregister(self, owned: OwnedObject):
        if isinstance(owned, PlayerEntity):
            self.map_observers.remove(owned)

    def get_notified(self, *args, **kwargs):
        pass

    @staticmethod
    @lru_cache
    @njit(['int64, int64, int64'], nogil=True, fastmath=True)
    def calculate_observable_area(pixel_x, pixel_y, visibility):
        visibility_radius = int(visibility // 1.5)
        observable_pixels = []
        add_to_observable = observable_pixels.append
        for x in range(-visibility_radius, visibility_radius):
            px = pixel_x + x
            abs_x = abs(x)
            for y in range(-visibility_radius, visibility_radius):
                radius = abs_x + abs(y)
                if radius < visibility:
                    py = pixel_y + y
                    add_to_observable((px, py))
        return observable_pixels
