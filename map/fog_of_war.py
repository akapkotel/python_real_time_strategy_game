#!/usr/bin/env python

from functools import lru_cache
from typing import Dict, KeysView, Optional, Set, Tuple

from arcade import Sprite, SpriteList, make_soft_circle_texture

from utils.colors import BLACK, FOG
from utils.data_types import GridPosition
from game import Game
from utils.constants import TILE_WIDTH, TILE_HEIGHT
from map.quadtree import Rect

OFFSET_X = TILE_WIDTH // 2
OFFSET_Y = TILE_HEIGHT // 2


DARK_TEXTURE = make_soft_circle_texture(3 * TILE_WIDTH, BLACK)
FOG_TEXTURE = make_soft_circle_texture(3 * TILE_WIDTH, FOG, 128)
FOG_SPRITELIST_SIZE = 60


class FogSprite(Sprite):

    def __init__(self, position, texture):
        super().__init__(center_x=position[0], center_y=position[1])
        self.texture = texture


class FogSpritePool:
    def __init__(self, size=100):
        self.dark_pool = [FogSprite((0, 0), DARK_TEXTURE) for _ in range(size)]
        self.fog_pool = [FogSprite((0, 0), FOG_TEXTURE) for _ in range(size)]
        self.dark_available = self.dark_pool.copy()
        self.fog_available = self.fog_pool.copy()

    def get_dark_sprite(self, position):
        if not self.dark_available:
            sprite = FogSprite(position, DARK_TEXTURE)
        else:
            sprite = self.dark_available.pop()
            sprite.center_x, sprite.center_y = position
        return sprite

    def get_fog_sprite(self, position):
        if not self.fog_available:
            sprite = FogSprite(position, FOG_TEXTURE)
        else:
            sprite = self.fog_available.pop()
            sprite.center_x, sprite.center_y = position
        return sprite

    def return_sprite(self, sprite):
        if sprite.texture == DARK_TEXTURE:
            self.dark_available.append(sprite)
        else:
            self.fog_available.append(sprite)


class FogOfWar(Rect):
    """
    TODO: merge this class with MiniMap (they use same GridPosition set)
    """
    game: Optional[Game] = None

    def __init__(self, cx=0, cy=0, width=0, height=0):
        width = self.game.map.width // self.game.map.grid_width
        height = self.game.map.height // self.game.map.grid_height
        x = width // 2
        y = height // 2
        super().__init__(x, y, width, height)

        self.fog_sprite_pool = FogSpritePool()

        # grid-data of the game-map:
        self.map_grids: KeysView[GridPosition] = self.game.map.nodes.keys()
        # Tiles which have not been revealed yet:
        self.unexplored: Set[GridPosition] = set([k for k in self.map_grids])

        # Tiles revealed in this frame:
        self.visible: Set[GridPosition] = set()
        # All tiles revealed to this moment:
        self.explored: Set[GridPosition] = set()

        # Dict to find and manipulate Sprites in the spritelist:
        self.grids_to_sprites: Dict[GridPosition, FogSprite] = {}
        # Black or semi-transparent grey sprites are drawn_area on the screen
        # width normal SpriteLists. We divide map for smaller areas with
        # distinct spritelists to avoid updating too large sets each frame:
        self.fog_sprite_lists = self.create_dark_sprites() if self.game.settings.fog_of_war else {}

    def in_bounds(self, item) -> bool:
        return self.left <= item[0] <= self.right and self.bottom <= item[1] <= self.top

    def create_dark_sprites(self, forced: bool = False) -> Dict[Tuple[int, int], SpriteList]:
        """
        Fill whole map with black tiles representing unexplored, hidden area.
        """
        cols, rows = self.game.map.columns // FOG_SPRITELIST_SIZE, self.game.map.rows // FOG_SPRITELIST_SIZE
        get_dark_sprite = self.fog_sprite_pool.get_dark_sprite
        sprite_lists = {}
        for col in range(cols+1):
            for row in range(rows+1):
                sprite_lists[(col, row)] = SpriteList(is_static=True)
        if (not self.game.editor_mode) or forced:
            get_tile_position = self.get_tile_position
            for x, y in self.unexplored:
                sprite_list = sprite_lists[(x // FOG_SPRITELIST_SIZE, y // FOG_SPRITELIST_SIZE)]
                # sprite = FogSprite(get_tile_position(x, y), DARK_TEXTURE)
                sprite = get_dark_sprite(get_tile_position(x, y))
                self.grids_to_sprites[(x, y)] = sprite
                sprite_list.append(sprite)
        return sprite_lists

    def reveal_nodes(self, revealed: Set[GridPosition]):
        """
        Call this method from each PlayerEntity, which is observing map,
        sending as param a set of GridPositions seen by the entity.
        """
        self.visible.update(revealed)

    def update(self):
        if not self.game.settings.fog_of_war:
            self.game.mini_map.visible = self.unexplored.union(self.explored)
            return
        # remove currently visible tiles from the fog-of-war:
        visible = self.visible
        grids_to_sprites = self.grids_to_sprites
        # since MiniMap also draws FoW, but the miniaturized version of, send
        # set of GridPositions revealed this frame to the MiniMap instance:
        self.game.mini_map.visible = revealed = visible.intersection(grids_to_sprites)
        for grid in revealed:
            sprite_list = self.fog_sprite_lists[(grid[0] // FOG_SPRITELIST_SIZE, grid[1] // FOG_SPRITELIST_SIZE)]
            sprite_list.remove(grids_to_sprites[grid])
            del grids_to_sprites[grid]
        # add grey-semi-transparent fog to the tiles which are no longer seen:
        fog = self.explored - visible
        get_tile_position = self.get_tile_position
        get_fog_sprite = self.fog_sprite_pool.get_fog_sprite
        for grid_x, grid_y in fog.difference(grids_to_sprites):
            x, y = get_tile_position(grid_x, grid_y)
            grids_to_sprites[(grid_x, grid_y)] = sprite = get_fog_sprite((x, y))  #  FogSprite((x, y), FOG_TEXTURE)
            sprite_list = self.fog_sprite_lists[(grid_x // FOG_SPRITELIST_SIZE, grid_y // FOG_SPRITELIST_SIZE)]
            sprite_list.append(sprite)
        self.explored.update(visible)
        self.unexplored.difference_update(visible)
        self.visible.clear()

    @staticmethod
    @lru_cache()
    def get_tile_position(x, y):
        return x * TILE_WIDTH + OFFSET_X, y * TILE_HEIGHT + OFFSET_Y

    # def draw(self):
    #     if self.game.editor_mode:
    #         return
    #     left, right, bottom, top = self.game.viewport
    #     screen_width, screen_height = left - right, top - bottom
    #
    #     for grid, sprite_list in self.fog_sprite_lists.items():
    #         s_left, s_right = grid[0] * screen_width, (grid[0] + 1) * screen_width
    #         s_bottom, s_top = grid[1] * screen_height, (grid[1] + 1) * screen_height
    #         if (left < s_right or right > s_left) and (bottom < s_top or top > s_bottom):
    #             sprite_list.draw()

    def draw(self):
        if self.game.editor_mode:
            return

        left, right, bottom, top = self.game.viewport

        # Pre-calculate which grid cells are visible in the viewport
        visible_grids = self._get_visible_grid_cells(left, right, bottom, top)

        # Only draw those sprite lists
        for grid in visible_grids:
            if grid in self.fog_sprite_lists:
                self.fog_sprite_lists[grid].draw()

    def _get_visible_grid_cells(self, left, right, bottom, top):
        # Calculate which grid cells are within the viewport
        # This could be cached if viewport hasn't changed
        screen_width, screen_height = left - right, top - bottom

        min_x = max(0, int(left / screen_width) - 1)
        max_x = min(int(self.game.map.columns // FOG_SPRITELIST_SIZE), int(right / screen_width) + 1)
        min_y = max(0, int(bottom / screen_height) - 1)
        max_y = min(int(self.game.map.rows // FOG_SPRITELIST_SIZE), int(top / screen_height) + 1)

        return [(x, y) for x in range(min_x, max_x + 1) for y in range(min_y, max_y + 1)]

    def __getstate__(self) -> Dict:
        saved_fow = self.__dict__.copy()
        del saved_fow['map_grids']
        del saved_fow['grids_to_sprites']
        del saved_fow['fog_sprite_lists']
        return saved_fow

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.map_grids = self.game.map.nodes.keys()
        self.grids_to_sprites = {}
        self.fog_sprite_lists = self.create_dark_sprites()
