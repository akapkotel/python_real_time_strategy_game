#!/usr/bin/env python

from typing import Optional, Tuple, List, Set, Collection

from arcade import (ShapeElementList, draw_rectangle_outline, draw_point,
                    create_rectangle_filled)
from arcade.arcade_types import Color

from game import Game

from utils.colors import WHITE, SAND
from utils.data_types import GridPosition


class MiniMap:
    game: Optional[Game] = None

    def __init__(self, data: Collection):
        self.loaded = len(data) > 4
        screen_size, minimap_size, tile_size, rows = data[:4]

        self.screen_size: Tuple[int, int] = screen_size
        self.width: int = minimap_size[0]
        self.height: int = minimap_size[1]
        self.rows: int = rows

        self.position = (
            screen_size[0] - (self.width // 2),
            screen_size[1] - (self.height // 2)
        )

        self.ratio = ratio = self.set_map_to_mini_map_ratio()

        self.tile_size = tile_size if self.loaded else (tile_size[0] * ratio, tile_size[1] * ratio)

        self.revealed_count = 0
        # cache visible to save
        self.drawn_area: Set[GridPosition] = set()

        self.drawn_entities: List[List[float, float, Color, int]] = []

        self.shapes_lists = self.create_shapes_lists()

        self.viewport = self.update_viewport()

        self.visible = set()

        if self.loaded:
            self.reveal_minimap_area(data[-1])

    def create_shapes_lists(self):
        """
        Create one ShapeElementList for each Map row, to avoid updating single,
        humongous list each time new MapNode is revealed. Smaller lists are
        updated faster.

        :return: List[ShapeElementList]
        """
        self.shapes_lists = {
            row: ShapeElementList() for row in range(self.rows)
        }
        dx, dy = self.minimap_left_and_bottom
        self.move_shapes_lists(dx + 5, dy + 65)
        return self.shapes_lists

    def set_map_to_mini_map_ratio(self) -> float:
        if self.height < self.width:
            return self.height / self.game.map.height
        else:
            return self.width / self.game.map.width

    def update(self):
        self.update_drawn_units()
        self.update_revealed_areas()
        self.visible.clear()

    def update_position(self, dx, dy):
        self.move_shapes_lists(dx, dy)
        _, right, _, top = self.game.viewport
        self.position = (right - 195, top - 95)
        self.viewport = self.update_viewport()

    def move_shapes_lists(self, dx, dy):
        shapes_list: ShapeElementList
        for shapes_list in self.shapes_lists.values():
            shapes_list.move(dx, dy)

    def update_viewport(self):
        x, y = self.game.window.screen_center
        return [
            self.position[0] - (self.width // 2) + (x * self.ratio),
            self.position[1] - (self.height // 2) + (y * self.ratio),
            (self.screen_size[0] - 400) * self.ratio,
            self.screen_size[1] * self.ratio
        ]

    def update_drawn_units(self):
        left, bottom = self.cached_left_and_bottom = self.minimap_left_and_bottom
        self.drawn_entities = [
            [left + (entity.center_x * self.ratio),
             bottom + (entity.center_y * self.ratio),
             entity.player.color, 4 if entity.is_building else 2]
            for entity in self.game.local_drawn_units_and_buildings
        ]
        # TODO: update building, draw terrain objects

    @property
    def minimap_left_and_bottom(self):
        return (self.position[0] - (self.width // 2),
                self.position[1] - (self.height // 2))

    def update_revealed_areas(self):
        revealed_this_time = self.visible.difference(self.drawn_area)
        self.drawn_area.update(revealed_this_time)
        self.reveal_minimap_area(revealed_this_time)

    def reveal_minimap_area(self, revealed_this_time):
        width, height = self.tile_size
        for (x, y) in revealed_this_time:
            shape = create_rectangle_filled(x * width, y * height, width, height, SAND)
            # MapNode y determines which ShapeElementList it should belong to:
            self.shapes_lists[y].append(shape)
        self.revealed_count += len(revealed_this_time)

    def draw(self):
        # draw revealed map areas:
        for shapes_list in self.shapes_lists.values():
            shapes_list.draw()
        for entity in self.drawn_entities:
            draw_point(*entity)
        # draw current viewport position on the game map:
        draw_rectangle_outline(*self.viewport, color=WHITE)

    def save(self):
        return [
            self.screen_size,
            (self.width, self.height),
            self.tile_size,
            self.rows,
            self.viewport,
            self.drawn_area,
        ]
