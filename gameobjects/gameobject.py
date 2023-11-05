#!/usr/bin/env python
from __future__ import annotations

from functools import cached_property
from typing import Optional, Union

from PIL import Image

from arcade import AnimatedTimeBasedSprite, load_texture, draw_rectangle_filled
from arcade.arcade_types import Point

from utils.constants import TILE_WIDTH, TILE_HEIGHT
from utils.colors import GREEN, RED, add_transparency
from utils.geometry import ROTATIONS
from utils.observer import Observed, Observer
from utils.functions import get_path_to_file, add_extension
from utils.game_logging import log_here
from utils.improved_spritelists import LayeredSpriteList
from utils.scheduling import EventsCreator, ScheduledEvent


def name_without_color(name: str) -> str:
    for color in ('_red', '_green', '_blue', '_yellow'):
        if name.endswith(color):
            return name.replace(color, '')
    return name


class GameObject(AnimatedTimeBasedSprite, EventsCreator, Observed):
    """
    GameObject represents all in-game objects, like units, buildings,
    terrain props, trees etc.
    """
    game = None
    total_objects_count = 0

    def __init__(self, texture_name: str,
                 position: Point = (0, 0),
                 object_id: Optional[int] = None,
                 observers: Optional[list[Observer]] = None):
        # raw name of the object without texture extension and Player color
        # used to query game.configs and as a basename to build other names
        self.object_name = name_without_color(texture_name)
        # name with texture extension added used to find ant load texture
        self.full_name = full_name = add_extension(texture_name)

        self.filename_with_path = self.game.resources_manager.get(full_name)

        super().__init__(self.filename_with_path, center_x=position[0], center_y=position[1])
        Observed.__init__(self, observers)
        EventsCreator.__init__(self)

        if object_id is None:
            GameObject.total_objects_count += 1
            self.id = GameObject.total_objects_count
        else:
            self.id = object_id
            GameObject.total_objects_count = max(GameObject.total_objects_count, object_id)

        self.is_updated = True
        self.is_rendered = True

        self.layered_spritelist: Optional[LayeredSpriteList] = None

    def __repr__(self) -> str:
        return f'{self.object_name} id: {self.id}'

    @property
    def timer(self):
        return self.game.timer

    @cached_property
    def text_hint(self) -> str:
        """
        Format and return string displayed when mouse cursor points at this
        object for time greater than Settings.hints_delay.
        """
        return self.object_name.title().replace('_', ' ')

    @property
    def on_screen(self) -> bool:
        l, r, b, t = self.game.viewport
        return self.right > l and self.left < r and self.top > b and self.bottom < t

    def on_update(self, delta_time: float = 1 / 60):
        self.position = [
            self._position[0] + self.change_x * delta_time,
            self._position[1] + self.change_y * delta_time
        ]
        self.update_visibility()

        if self.frames and self.is_rendered:
            self.update_animation(delta_time)

    def update_visibility(self):
        if self.should_be_rendered:
            if not self.is_rendered:
                self.start_rendering()
        elif self.is_rendered:
            self.stop_rendering()

    @property
    def should_be_rendered(self) -> bool:
        return self.on_screen

    def start_rendering(self):
        # log(f'Start rendering {self}', True)
        self.is_rendered = True
        self.alpha = 255

    def stop_rendering(self):
        # log(f'Stop rendering {self}', True)
        self.is_rendered = False
        self.alpha = 0

    def start_updating(self):
        self.is_updated = True

    def stop_updating(self):
        self.is_updated = False

    def on_mouse_enter(self):
        pass

    def on_mouse_exit(self):
        pass

    def kill(self):
        log_here(f'Destroying GameObject: {self}', True)
        try:
            self.layered_spritelist.remove(self)
        except (AttributeError, ValueError):
            pass
        finally:
            self.detach_observers()
            super().kill()

    def save(self) -> dict:
        """We save only simple data-types required to respawn original GameObject, instead of pickling it."""
        return {
            'id': self.id,
            'object_name': self.object_name,
            'position': self._position,  # (self.center_x, self.center_y)
        }


class TerrainObject(GameObject):

    def __init__(self, filename: str, durability: int, position: Point):
        GameObject.__init__(self, filename, position)
        self.map_node = self.game.map.position_to_node(*self.position)
        if durability:
            self.map_node.static_gameobject = self
        self.attach(observer=self.game)

    def draw(self):
        # TerrainObjects are not updated, so we need check here if to render
        if self.on_screen:
            super().draw()

    def kill(self):
        self.map_node.static_gameobject = None
        super().kill()


class Tree(TerrainObject):

    def __init__(self, filename: str, durability: int, position: Point):
        super().__init__(filename, durability, position)
        self.map_node.tree = self

    def kill(self):
        self.map_node.tree = None
        super().kill()

    def save(self) -> int:
        # Tree is saved as the integer ending it's texture name, to avoid saving weakref to the MapNode
        return int(self.object_name[-1])


class Wreck(TerrainObject):

    def __init__(self, filename: str, durability: int, position: Point, texture_index: Union[tuple, int]):
        super().__init__(filename, durability, position)
        lifetime = self.game.settings.remove_wrecks_after_seconds
        self.set_proper_wreck_texture(filename, texture_index)
        self.schedule_event(ScheduledEvent(creator=self, delay=lifetime, function=self.kill))

    def __repr__(self) -> str:
        return f'Wreck(id: {self.id})'

    def set_proper_wreck_texture(self, name, texture_index):
        texture_name = get_path_to_file(name)
        width, height = Image.open(texture_name).size
        try:  # for tanks with turrets
            i, j = texture_index  # Tuple
            self.texture = load_texture(
                texture_name, j * (width // ROTATIONS), i * (height // ROTATIONS), width // ROTATIONS, height // ROTATIONS)
        except TypeError:
            self.texture = load_texture(
                texture_name, texture_index * (width // ROTATIONS), 0, width // ROTATIONS, height)


class Corpse(Wreck):

    def __init__(self, filename: str, durability: int, position: Point, texture_index: Union[tuple, int]):
        super().__init__(filename, durability, position, texture_index)

    def __str__(self) -> str:
        return f'Corpse(id: {self.id})'


class PlaceableGameObject:
    """
    This class generates a semi-transparent gizmo of Building showing to player if its construction is possible and how
    much space is required to build the object.
    """

    def __init__(self, gameobject_name: str, player, x, y):
        self.game = player.game
        self.player = player
        self.gameobject_name = gameobject_name
        self.position = x, y
        self.grid_width, self.grid_height = self.game.configs[gameobject_name]['size']
        self.last_grid = None
        self.grids = None
        self.drawn_gizmo_data = None

    def snap_to_the_map_grid(self, gx: int, gy: int, forced=False):
        """
        Create dictionary of map positions and their boolean 'availabilities' for constructing Building. This dict would
        be used to draw colored gizmo on the screen when player seek a proper position for placing the Building.
        """
        if not forced and self.last_grid == (gx, gy):
            return
        from map.map import map_grid_to_position
        self.position = map_grid_to_position((gx + 1, gy + 1))  # TODO: find why and where this offset happens
        self.grids = {
            map_grid_to_position((gx + x, gy + y)): self.game.map.node((gx + x, gy + y)).available_for_construction
            for y in range(self.grid_height) for x in range(self.grid_width)
        }
        self.last_grid = gx, gy

    def update(self):
        if not self.grids:
            return
        self.drawn_gizmo_data = (
            (gx, gy, TILE_WIDTH, TILE_HEIGHT, add_transparency(GREEN if is_available else RED, 64))
            for (gx, gy), is_available in self.grids.items()
        )

    def draw(self):
        for grid_data in self.drawn_gizmo_data:
            draw_rectangle_filled(*grid_data)

    def is_construction_possible(self) -> bool:
        if self.is_location_available:
            return self.game.settings.editor_mode or self.player.enough_resources_for(self.gameobject_name)
        return False

    @property
    def is_location_available(self) -> bool:
        if self.grids:
            return all(bool(availability) for availability in self.grids.values())
        return False

    def build(self):
        if self.game.editor_mode:
            self.game.spawn(self.gameobject_name, self.player, self.position)
            self.game.units_manager.unselect_all_selected()
        else:
            from buildings.buildings import ConstructionSite
            ConstructionSite(self.gameobject_name, self.player, self.position)
        self.snap_to_the_map_grid(*self.last_grid, forced=True)
