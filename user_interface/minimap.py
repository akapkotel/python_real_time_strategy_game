#!/usr/bin/env python
from typing import Optional, Tuple, List, Set, Union, Dict

from arcade import (ShapeElementList, draw_rectangle_outline, draw_point,
                    create_rectangle_filled)
from arcade.arcade_types import Color

from game import Game

from utils.colors import WHITE, SAND, RED, BLACK, GREEN
from utils.data_types import GridPosition


MARGIN_TOP = 7  # since our mini-map area is distanced little from screen edges
MARGIN_RIGHT = 7


class MiniMap:
    game: Optional[Game] = None

    def __init__(self, data: Union[List, Tuple], loaded=False):
        """
        This class displays a little map-representation in the user interface
        to allow player to faster navigate on the map and know, where are his
        units etc. Assign it to the mini_map attribute of the Game class.

        :param data: List -- accepts a list of values, if Game is loaded from
        file, e.g. when player loads saved game, list contains 6 elements, or 4
        otherwise.
        :param loaded: bool -- whether minimap is loaded from file. Defaults to
        False.
        """
        self.loaded = loaded
        screen_size, minimap_size, tile_size, rows = data[:4]

        self.screen_width: int = screen_size[0]
        self.screen_height: int = screen_size[1]
        self.max_width: int = minimap_size[0]
        self.half_max_width: int = self.max_width // 2
        self.max_height: int = minimap_size[1]
        self.half_max_height: int = self.max_height // 2
        self.rows: int = rows

        self.ratio = ratio = self.set_map_to_mini_map_ratio()
        self.width = self.game.map.width * ratio
        self.half_width = self.width // 2
        self.height = self.game.map.height * ratio
        self.half_height = self.height // 2

        self.position = self.get_position()
        self.minimap_bounds = self.update_bounds()

        self.tile_size = tile_size if self.loaded else (tile_size[0] * ratio,
                                                        tile_size[1] * ratio)

        self.viewport = self.update_viewport()

        # cache visible map area for saving it:
        self.drawn_area: Set[GridPosition] = set()
        self.drawn_entities: List[List[float, float, Color, int]] = []
        self.shapes_lists = self.create_shapes_lists()

        self.visible = set()

        self.reveal_minimap_area(self.game.fog_of_war.explored)

    def set_map_to_mini_map_ratio(self) -> float:
        """
        To make sure that mini-map would fit into the interface slot, calculate
        a common ratio used to translate both map dimensions from world to
        mini-map and pick ratio for smaller world-map dimension.
        """
        return min(self.max_height / self.game.map.height,
                   self.max_width / self.game.map.width)

    def create_shapes_lists(self) -> Dict[int, ShapeElementList]:
        """
        Create one ShapeElementList for each Map row, to avoid updating single,
        humongous list each time new MapNode is revealed. Smaller lists are
        updated faster.
        """
        self.shapes_lists = {
            row: ShapeElementList() for row in range(self.rows)
        }
        # if self.loaded:
        r, t = self.screen_width, self.screen_height
        dx, dy = r - self.half_max_width - self.half_width, t - self.half_max_height - self.half_height
        # else:
        #     dx, dy, *_ = self.minimap_bounds
        self.move_shapes_lists(dx + 2, dy + 53)
        return self.shapes_lists

    def update(self):
        if self.game.settings.show_minimap:
            self.update_drawn_units()
            self.update_revealed_areas()
            self.visible.clear()

    def update_position(self, dx: float, dy: float):
        self.move_shapes_lists(dx, dy)
        self.position = self.get_position()
        self.minimap_bounds = self.update_bounds()
        self.viewport = self.update_viewport()

    def get_position(self):
        _, right, _, top = self.game.viewport
        return right - (self.half_max_width + MARGIN_RIGHT), top - (self.half_max_height + MARGIN_TOP)

    def move_shapes_lists(self, dx: float, dy: float):
        shapes_list: ShapeElementList
        for shapes_list in self.shapes_lists.values():
            shapes_list.move(dx, dy)

    def update_viewport(self):
        x, y = self.game.window.screen_center
        left, bottom, *_ = self.minimap_bounds
        return [
            left + ((x - 200) * self.ratio),
            bottom + (y * self.ratio),
            (self.screen_width - 400) * self.ratio,
            self.screen_height * self.ratio,
        ]

    def update_drawn_units(self):
        left, bottom, *_ = self.minimap_bounds
        ratio = self.ratio
        self.drawn_entities = [
            [left + (entity.center_x * ratio),
             bottom + (entity.center_y * ratio),
             entity.player.color, 4 if entity.is_building else 2]
            for entity in self.game.local_drawn_units_and_buildings
        ]
        # TODO: update building, draw terrain objects

    def update_bounds(self):
        return (self.position[0] - self.half_width,
                self.position[1] - self.half_height,
                self.position[0] + self.half_width,
                self.position[1] + self.half_height)

    def update_revealed_areas(self):
        revealed_this_time = self.visible.difference(self.drawn_area)
        self.drawn_area.update(revealed_this_time)
        self.reveal_minimap_area(revealed_this_time)

    def reveal_minimap_area(self, revealed_this_time: Set[GridPosition]):
        width, height = self.tile_size
        for row, shape_list in self.shapes_lists.items():
            append = shape_list.append
            [append(create_rectangle_filled(grid_x * width, grid_y * height, width, height, SAND))
             for (grid_x, grid_y) in (grid for grid in revealed_this_time if grid[1] is row)]

    def draw(self):
        # draw revealed map areas:
        for shapes_list in self.shapes_lists.values():
            shapes_list.draw()
        for entity in self.drawn_entities:
            draw_point(*entity)
        # draw current viewport position on the game map:
        draw_rectangle_outline(*self.viewport, color=WHITE)
        draw_rectangle_outline(*self.position, self.width, self.height, RED, 1)

    def cursor_over_minimap(self, x: float, y: float) -> Optional[Tuple[float, float]]:
        """
        Check if mouse cursor points at the MiniMap area, if so, return the
        pointed position translated from minimap's to world dimensions.
        """
        left, bottom, right, top = self.minimap_bounds
        if left < x < right and bottom < y < bottom + top:
            return (x - left) // self.ratio, (y - bottom) // self.ratio

    def create_minimap_texture(self):
        """
        Generate a texture for the minimap, which will be saved in the saved game or scenario file to be used as a
        miniature in the game menu, when player is browsing saved games and scenarios.
        """
        from PIL import Image, ImageDraw
        image = Image.new(mode='RGBA', size=(int(self.width), int(self.height)), color=(75, 75, 75, 50))
        draw = ImageDraw.Draw(image, 'RGBA')

        # draw revealed map area
        width, height = self.tile_size
        [draw.regular_polygon((x * width, y * height, 2), 4, fill=(0, 255, 0, 50)) for (x, y) in self.drawn_area]

        # draw viewport:
        x, y, width, height = (int(x) for x in self.viewport)
        lt = x - width / 2, y + height / 2
        rt = x + width / 2, y + height / 2
        rb = x + width / 2, y - height / 2
        lb = x - width / 2, y - height / 2
        draw.line([lt, rt, rt, rb, rb, lb, lb, lt], fill=WHITE)

        # draw units
        left, bottom, *_ = self.minimap_bounds
        for color in (GREEN, RED):
            draw.point(
                [(int(entity[0] - left), int(entity[1] - bottom))
                 for entity in self.drawn_entities if entity[2] == color], fill=color
            )
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        return image

    def save(self):
        return [
            (self.screen_width, self.screen_height),
            (self.max_width, self.max_height),
            self.tile_size,
            self.rows,
        ]
