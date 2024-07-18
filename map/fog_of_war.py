#!/usr/bin/env python

from functools import lru_cache
from typing import Dict, KeysView, Optional, Set, Tuple

from arcade import Sprite, SpriteList, make_soft_circle_texture

from utils.colors import BLACK, FOG
from utils.data_types import GridPosition
from game import Game
from utils.constants import TILE_WIDTH
from map.quadtree import Rect

DARK_TEXTURE = make_soft_circle_texture(2 * TILE_WIDTH, BLACK)
FOG_TEXTURE = make_soft_circle_texture(2 * TILE_WIDTH, FOG, 128)
FOG_SPRITELIST_SIZE = 60


class FogSprite(Sprite):

    def __init__(self, position, texture):
        super().__init__(center_x=position[0], center_y=position[1])
        self.texture = texture


class FogOfWar(Rect):
    """
    TODO: merge this class with MiniMap (they use same GridPosition set)
    """
    game: Optional[Game] = None

    def __init__(self):
        width = self.game.map.width
        height = self.game.map.height
        x = width // 2
        y = height // 2
        self.fog_tile_size = self.game.map.tile_width
        super().__init__(x, y, width, height)

        # grid-data of the game-map:
        # self.map_grids: KeysView[GridPosition] = self.game.map.tiles.keys()
        # Tiles which have not been revealed yet:
        self.unexplored: Set[GridPosition] = set(self.game.map.tiles.keys())
        self.explored: Set[GridPosition] = set()
        self.visible: Set[GridPosition] = set()

        # Dict to find and manipulate Sprites in the spritelist:
        self.grids_to_sprites: Dict[GridPosition, FogSprite] = {}
        self.fog_sprite_lists = self.create_dark_sprites()

    def in_bounds(self, item) -> bool:
        return self.left <= item[0] <= self.right and self.bottom <= item[1] <= self.top

    @lru_cache()
    def get_tile_position(self, grid: Tuple[int, int]):
        return self.game.map.grid_to_positions(grid)

    def create_dark_sprites(self, forced: bool = False) -> Dict[Tuple[int, int], SpriteList]:
        """
        Fill whole map with black tiles representing unexplored, hidden area.
        """
        cols, rows = self.game.map.columns // FOG_SPRITELIST_SIZE, self.game.map.rows // FOG_SPRITELIST_SIZE
        sprite_lists = {}
        for col in range(cols+1):
            for row in range(rows+1):
                sprite_lists[(col, row)] = SpriteList(is_static=True)
        if (not self.game.editor_mode) or forced:
            get_tile_position = self.game.map.grid_to_positions
            for x, y in self.unexplored:
                sprite_list = sprite_lists[(x // FOG_SPRITELIST_SIZE, y // FOG_SPRITELIST_SIZE)]
                sprite = FogSprite(get_tile_position((x, y)), DARK_TEXTURE)
                self.grids_to_sprites[(x, y)] = sprite
                sprite_list.append(sprite)
        return sprite_lists

    def reveal_visible_nodes(self, revealed: Set[GridPosition]):
        """
        Call this method from each PlayerEntity, which is observing map,
        sending as param a set of GridPositions seen by the entity.
        """
        self.visible.update(revealed)

    def update(self):
        visible = self.visible
        grids_to_sprites = self.grids_to_sprites
        fog_sprite_lists = self.fog_sprite_lists
        self.game.mini_map.visible = revealed = visible.intersection(grids_to_sprites)
        self.show_visible_tiles(fog_sprite_lists, grids_to_sprites, revealed)

        get_tile_position = self.game.map.grid_to_positions
        self.hide_not_visible_tiles(visible, fog_sprite_lists, get_tile_position, grids_to_sprites)
        self.explored.update(visible)
        self.unexplored.difference_update(visible)
        self.visible = set()

    @staticmethod
    def show_visible_tiles(fog_sprite_lists, grids_to_sprites, revealed):
        for grid in revealed:
            sprite_list = fog_sprite_lists[(grid[0] // FOG_SPRITELIST_SIZE, grid[1] // FOG_SPRITELIST_SIZE)]
            sprite_list.remove(grids_to_sprites[grid])
            del grids_to_sprites[grid]

    def hide_not_visible_tiles(self, visible, fog_sprite_lists, get_tile_position, grids_to_sprites):
        fog = self.explored.difference(visible)
        for grid in fog.difference(grids_to_sprites):
            x, y = get_tile_position(grid)
            grids_to_sprites[grid] = sprite = FogSprite((x, y), FOG_TEXTURE)
            sprite_list = fog_sprite_lists[(grid[0] // FOG_SPRITELIST_SIZE, grid[1] // FOG_SPRITELIST_SIZE)]
            sprite_list.append(sprite)

    def draw(self):
        if self.game.editor_mode:
            return
        left, right, bottom, top = self.game.viewport
        screen_width, screen_height = left - right, top - bottom

        for grid, sprite_list in self.fog_sprite_lists.items():
            s_left, s_right = grid[0] * screen_width, (grid[0] + 1) * screen_width
            s_bottom, s_top = grid[1] * screen_height, (grid[1] + 1) * screen_height
            if (left < s_right or right > s_left) and (bottom < s_top or top > s_bottom):
                sprite_list.draw()

    def __getstate__(self) -> Dict:
        saved_fow = self.__dict__.copy()
        del saved_fow['map_grids']
        del saved_fow['grids_to_sprites']
        del saved_fow['fog_sprite_lists']
        return saved_fow

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.map_grids = self.game.map.tiles.keys()
        self.grids_to_sprites = {}
        self.fog_sprite_lists = self.create_dark_sprites()
