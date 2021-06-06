#!/usr/bin/env python

from typing import Optional, Tuple, List, Set, Union

from arcade import (ShapeElementList, draw_rectangle_outline, draw_point,
                    create_rectangle_filled)
from arcade.arcade_types import Color

from game import Game

from utils.colors import WHITE, SAND, RED
from utils.data_types import GridPosition


MARGIN_TOP = 5  # since our mini-map area is distanced little from screen edges
MARGIN_RIGHT = 5


class MiniMap:
    game: Optional[Game] = None

    def __init__(self, data: Union[List, Tuple]):
        """
        This class displays a little map-representation in the user interface
        to allow player to faster navigate on the map and know, where are his
        units etc. Assign it to the mini_map attribute of the Game class.

        :param data: List -- accepts a list of values, if Game is loaded from
        file, eg. when player loads saved game, list contains 6 elements, or 4
        otherwise.
        """
        self.loaded = len(data) > 4
        screen_size, minimap_size, tile_size, rows = data[:4]

        self.screen_width: int = screen_size[0]
        self.screen_height: int = screen_size[1]
        self.max_width: int = minimap_size[0]
        self.max_height: int = minimap_size[1]
        self.rows: int = rows

        self.ratio = ratio = self.set_map_to_mini_map_ratio()
        self.width = self.game.map.width * ratio
        self.height = self.game.map.height * ratio

        self.position = self.get_position()

        self.tile_size = tile_size if self.loaded else (tile_size[0] * ratio, tile_size[1] * ratio)

        self.revealed_count = 0

        # cache visible map area for saving it:
        self.drawn_area: Set[GridPosition] = set()

        self.drawn_entities: List[List[float, float, Color, int]] = []

        self.viewport = self.update_viewport()

        self.shapes_lists = self.create_shapes_lists()

        self.visible = set()

        if self.loaded:
            self.reveal_minimap_area(data[-1])

    def set_map_to_mini_map_ratio(self) -> float:
        """
        To make sure that mini-map would fit into the interface slot, calculate
        a common ratio used to translate both map dimensions from world to
        mini-map and pick ratio for smaller world-map dimension.
        """
        if self.game.map.width < self.game.map.height:
            return self.max_width / self.game.map.width
        else:
            return self.max_height / self.game.map.height

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
        self.move_shapes_lists(dx + 11, dy + 60)
        return self.shapes_lists

    def update(self):
        self.update_drawn_units()
        self.update_revealed_areas()
        self.visible.clear()

    def update_position(self, dx, dy):
        self.move_shapes_lists(dx, dy)
        self.position = self.get_position()
        self.viewport = self.update_viewport()

    def get_position(self):
        _, right, _, top = self.game.viewport
        return (right - self.max_width // 2 - MARGIN_RIGHT,
               top - self.max_height // 2 - MARGIN_TOP)

    def move_shapes_lists(self, dx, dy):
        shapes_list: ShapeElementList
        for shapes_list in self.shapes_lists.values():
            shapes_list.move(dx, dy)

    def update_viewport(self):
        x, y = self.game.window.screen_center
        left, bottom = self.minimap_left_and_bottom
        return [
            left + ((x - 200) * self.ratio),
            bottom + (y * self.ratio),
            (self.screen_width - 400) * self.ratio,
            self.screen_height * self.ratio
        ]

    def update_drawn_units(self):
        left, bottom = self.minimap_left_and_bottom
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

    def reveal_minimap_area(self, revealed_this_time: Set[GridPosition]):
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
        draw_rectangle_outline(*self.position, self.width, self.height, RED, 1)

    def save(self):
        return [
            (self.screen_width, self.screen_height),
            (self.width, self.height),
            self.tile_size,
            self.rows,
            self.viewport,
            self.drawn_area
        ]
