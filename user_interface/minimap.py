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

    def __init__(self, data: Union[List, Tuple], loaded=False):
        """
        This class displays a little map-representation in the user interface
        to allow player to faster navigate on the map and know, where are his
        units etc. Assign it to the mini_map attribute of the Game class.

        :param data: List -- accepts a list of values, if Game is loaded from
        file, eg. when player loads saved game, list contains 6 elements, or 4
        otherwise.
        """
        self.loaded = loaded
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

        self.tile_size = tile_size if self.loaded else (tile_size[0] * ratio,
                                                        tile_size[1] * ratio)

        self.viewport = self.update_viewport()

        # cache visible map area for saving it:
        self.drawn_area: Set[GridPosition] = set()
        self.drawn_entities: List[List[float, float, Color, int]] = []
        self.shapes_lists = self.create_shapes_lists()

        self.visible = set()
        self.revealed_count = 0
        self.reveal_minimap_area(self.game.fog_of_war.explored)

    def set_map_to_mini_map_ratio(self) -> float:
        """
        To make sure that mini-map would fit into the interface slot, calculate
        a common ratio used to translate both map dimensions from world to
        mini-map and pick ratio for smaller world-map dimension.
        """
        return min(self.max_height / self.game.map.height,
                   self.max_width / self.game.map.width)

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
        if self.loaded:
            r, t = self.screen_width - MARGIN_RIGHT, self.screen_height - MARGIN_TOP
            dx, dy = r - self.max_width // 2 - self.width // 2, t - self.max_height
        else:
            dx, dy = self.minimap_left_and_bottom
        self.move_shapes_lists(dx + 9, dy + 60)
        return self.shapes_lists

    def update(self):
        self.update_drawn_units()
        self.update_revealed_areas()
        self.visible.clear()

    def update_position(self, dx: float, dy: float):
        self.move_shapes_lists(dx, dy)
        self.position = self.get_position()
        self.viewport = self.update_viewport()

    def get_position(self):
        _, right, _, top = self.game.viewport
        right, top = right - MARGIN_RIGHT, top - MARGIN_TOP
        return right - self.max_width // 2, top - self.max_height // 2

    def move_shapes_lists(self, dx: float, dy: float):
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
            self.screen_height * self.ratio,
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
        w, h = self.tile_size
        for (x, y) in revealed_this_time:
            shape = create_rectangle_filled(x * w, y * h, w, h, SAND)
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

    def cursor_inside(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """
        Check if mouse cursor points at the MiniMap area, if so, return the
        pointed position translated from minimap's to world dimensions.
        """
        left, bottom = self.minimap_left_and_bottom
        if left < x < left + self.width and bottom < y < bottom + self.height:
            return (x - left) // self.ratio, (y - bottom) // self.ratio

    def save(self):
        return [
            (self.screen_width, self.screen_height),
            (self.max_width, self.max_height),
            self.tile_size,
            self.rows,
        ]
