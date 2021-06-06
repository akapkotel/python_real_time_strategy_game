#!/usr/bin/env python

from typing import Optional

from arcade import (
    ShapeElementList, create_line, draw_circle_outline, draw_text, draw_line,
    draw_rectangle_filled,
)

from game import TILE_HEIGHT, TILE_WIDTH
from utils.colors import RED, GREEN, WHITE, BLACK
from utils.functions import to_rgba
from utils.logging import log
from units.units import Unit


class GameDebugger:
    """
    This class is a simple tool used to draw on the screen things, that are not
    visible in the actual gameplay (and should not be) to help debugging.
    """
    game = None
    log = None  # TODO: get log text from log/logger
    debug_mouse = True
    debug_map = True
    debug_units = True
    debug_pathfinding = True
    debugged = []
    map_grid: Optional[ShapeElementList] = None

    def __init__(self):
        settings = self.game.settings.__dict__
        for name in (n for n in settings if hasattr(self, n)):
            log(f'Setting: {name} set to {settings[name]}', 1)
            setattr(self, name, settings[name])

    def update(self):
        self.debugged.clear()
        if self.debug_map and self.map_grid is None:
            self.map_grid = self.create_map_debug_grid()
        if self.debug_mouse:
            position = self.game.window.cursor.position
            grid = self.game.map.position_to_grid(*position)
            self.log = f'Mouse at: {position}, node: {grid}'

    def draw(self):
        if self.debug_map:
            self.draw_debugged_map_grid()
        if self.debug_mouse:
            self.draw_debugged_mouse_pointed_nodes()
        self.draw_debugged()
        self.draw_log()

    def create_map_debug_grid(self) -> ShapeElementList:
        grid = ShapeElementList()
        h_offset = TILE_HEIGHT // 2
        w_offset = TILE_WIDTH // 2
        # horizontal lines:
        for i in range(self.game.map.rows):
            y = i * TILE_HEIGHT
            h_line = create_line(0, y, self.game.map.width, y, BLACK)
            grid.append(h_line)

            y = i * TILE_HEIGHT + h_offset
            h2_line = create_line(w_offset, y, self.game.map.width, y, WHITE)
            grid.append(h2_line)
        # vertical lines:
        for j in range(self.game.map.columns * 2):
            x = j * TILE_WIDTH
            v_line = create_line(x, 0, x, self.game.map.height, BLACK)
            grid.append(v_line)

            x = j * TILE_WIDTH + w_offset
            v2_line = create_line(x, h_offset, x, self.game.map.height, WHITE)
            grid.append(v2_line)
        return grid

    def draw_debugged_map_grid(self):
        self.map_grid.draw()

    def draw_debugged_mouse_pointed_nodes(self):
        position = self.game.map.normalize_position(*self.game.window.cursor.position)
        node = self.game.map.position_to_node(*position)

        draw_circle_outline(node.x, node.y, 10, RED, 2)

        for adj in node.adjacent_nodes + [node]:
            color = to_rgba(WHITE, 25) if adj.walkable else to_rgba(RED, 25)
            draw_rectangle_filled(adj.x, adj.y, TILE_WIDTH, TILE_HEIGHT, color)
            draw_circle_outline(*adj.position, 5, color=WHITE, border_width=1)

    def draw_debugged(self):
        self.draw_debug_paths()
        self.draw_debug_lines_of_sight()
        self.draw_debug_units()

    def draw_debug_units(self):
        unit: Unit
        for unit in self.game.units:
            x, y = unit.position
            draw_text(str(unit.id), x, y + 40, color=GREEN)
            if (target := unit.targeted_enemy) is not None:
                draw_text(str(target.id), x, y - 40, color=RED)

    def draw_debug_paths(self):
        for path in (u.path for u in self.game.local_human_player.units if u.path):
            for i, point in enumerate(path):
                try:
                    end = path[i + 1]
                    draw_line(*point, *end, color=GREEN, line_width=1)
                except IndexError:
                    pass

    def draw_debug_lines_of_sight(self):
        for unit in (u for u in self.game.local_human_player.units if u.known_enemies):
            for enemy in unit.known_enemies:
                draw_line(*unit.position, *enemy.position, color=RED)

    def draw_log(self):
        if self.log is not None:
            x, _, y, _ = self.game.viewport
            draw_rectangle_filled(x + 100, y + 25, 200, 50, BLACK)
            draw_text(self.log, x + 10, y + 20, WHITE)
