#!/usr/bin/env python

from functools import lru_cache
from typing import Sequence, List, Set, Tuple, Optional
from numba import njit
from arcade import SpriteSolidColor, SpriteList, ShapeElementList, are_polygons_intersecting
from arcade.arcade_types import Point

from game import Game, SCREEN_WIDTH, SCREEN_HEIGHT
from observers import ObjectsOwner, OwnedObject
from player import PlayerEntity
from colors import FOG, BLACK
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
        self.black_rectangles = SpriteList(is_static=True)
        self.grey_rectangles = SpriteList(is_static=True)
        self.black_rectangles.append(FogRectangle(0, 0, width, height, BLACK))
        self.grey_rectangles.append(FogRectangle(0, 0, width, height, FOG))

        self.black_fog_pixels: Set[Point] = set()
        self.grey_fog_pixels: Set[Point] = set()
        self.all_fog_pixels = ShapeElementList()
        self.map_observers: List[PlayerEntity] = []
        log(f'FogOfWar created. Fog objects: {len(self)}')

    def __len__(self):
        return self.fog_rectangles_count + self.fog_pixels_count

    def register(self, acquired: OwnedObject):
        acquired: PlayerEntity
        self.map_observers.append(acquired)
        log(f'Registered new observer: {acquired}')

    def unregister(self, owned: OwnedObject):
        if isinstance(owned, PlayerEntity):
            self.map_observers.remove(owned)

    def get_notified(self, *args, **kwargs):
        pass

    @property
    def fog_rectangles_count(self):
        return len(self.black_rectangles) + len(self.grey_rectangles)

    @property
    def fog_pixels_count(self):
        return len(self.black_fog_pixels) + len(self.grey_fog_pixels)

    def update(self):
        # all_fog_rects = self.get_all_fog_rectangles()
        # find all square-areas around GameEntities which moved this frame
        for rect in self.get_observed_rects():
            colliding_fogs = [
                fog_rect for fog_rect in self.get_all_fog_rectangles() if
                are_polygons_intersecting(rect, fog_rect.hit_box)
            ]
            # print(f'Collliding: {colliding_fogs}')
            for fog in colliding_fogs:
                try:
                    self.black_rectangles.remove(fog)
                except ValueError:
                    self.grey_rectangles.remove(fog)

                self.divide_fog(fog, rect)

    def divide_fog(self, fog: FogRectangle, observed_rect: Sequence[Point]):
        new_fogs: List[FogRectangle] = []

    def get_all_fog_rectangles(self) -> List[FogRectangle]:
        return self.black_rectangles.sprite_list + self.grey_rectangles.sprite_list

    def get_observed_rects(self) -> List[Tuple[Point, Point, Point, Point]]:
        observed_rectangles = []
        for observer in self.map_observers:
            x, y = observer.center_x, observer.center_y
            w = h = observer.visibility_radius
            observed_rect = ((x-w, y-h), (x+w, y-h), (x+w, y+h), (x-w, y+h))
            observed_rectangles.append(observed_rect)
        return observed_rectangles

    def get_colliding_fog_rects(self, all_fog_rects,observed_rects):
        return sorted([
            (fog_rect, observed_rect) for fog_rect in all_fog_rects for
            observed_rect in observed_rects if
            are_polygons_intersecting(observed_rect, fog_rect.hit_box)
        ], key=lambda e: e[1][0])

    def recalculate_fog_rectangles(self, colliding_fog_rects):
        for fog_rect, observed_rect in colliding_fog_rects:
            print(f'Recalculating pair: {fog_rect, observed_rect}')

            # one rect inside another:

            # one rect enters from the side:

            # one rect enters from the corner:

    def fill_voids_with_fog_pixels(self):
        for pixel in self.grey_fog_pixels.union(self.black_fog_pixels):
            pass

    def draw(self):
        # self.draw_fog_rectangles()
        self.draw_fog_pixels()

    def draw_fog_rectangles(self):
        for rectangles in (self.grey_rectangles, self.black_rectangles):
            rectangles.draw()

    def draw_fog_pixels(self):
        self.all_fog_pixels.draw()

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
