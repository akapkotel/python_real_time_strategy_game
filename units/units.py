#!/usr/bin/env python
from __future__ import annotations

import random
import time
from enum import IntEnum

from math import dist
from abc import abstractmethod, ABC
from collections import deque, defaultdict
from functools import cached_property
from typing import Deque, List, Dict, Optional, Union

from arcade import (
    Sprite, load_textures, draw_circle_filled, draw_circle_outline,draw_text, Texture, load_texture, draw_line
)
from arcade.arcade_types import Point

from utils.constants import EXPLOSION, MapPath, UI_UNITS_PANEL
from effects.explosions import Explosion
from map.map import (
    GridPosition, MapNode, Pathfinder, normalize_position,
    position_to_map_grid, TerrainType, map_grid_to_position
)
from players_and_factions.player import Player, PlayerEntity
from user_interface.user_interface import UiElement, UiTextLabel
from utils.colors import GREEN, value_to_color
from utils.functions import (get_path_to_file, get_texture_size, ignore_in_editor_mode)
from utils.game_logging import log_here
from utils.geometry import (
    precalculate_possible_sprites_angles, calculate_angle,
    vector_2d, ROTATION_STEP, ROTATIONS
)


__all__ = ['Unit', 'Vehicle', 'VehicleWithTurret', 'Boat', 'BoatWithTurret', 'AirUnit', 'Soldier']


CLOSE_ENOUGH_DISTANCE = 0.1


class UnitActivity(IntEnum):
    IDLE = 0
    MOVE = 1
    ATTACK = 2
    DIE = 3


class Unit(PlayerEntity, ABC):
    """
    Unit is a PlayerEntity which can move on map.
    """
    angles = precalculate_possible_sprites_angles()

    def __init__(self,
                 unit_name: str,
                 player: Player,
                 weight: int,
                 position: Point,
                 object_id: Optional[int] = None):
        PlayerEntity.__init__(self, unit_name, player, position, object_id=object_id)
        # since we can not rotate actual sprite when Unit rotates, we replace its texture each time the Unit rotates for
        # texture showing Unit rotated in actual direction. We calculate a virtual 'angle' Unit is rotated, and use it
        # to pick one of the 16 possible rotations among its textures
        self.current_activity = UnitActivity.IDLE
        self.facing_direction = random.randint(0, ROTATIONS - 1)
        self.virtual_angle = int(ROTATION_STEP * self.facing_direction) % 360

        self.weight = weight

        # pathfinding and map-related:
        self.position = normalize_position(*self.position)
        self.reserved_node = None
        self.current_node = self.map.position_to_node(*self.position)
        self.block_map_node(self.current_node)

        self.forced_destination = False
        self.path: Deque[GridPosition] = deque()
        self.path_wait_counter: int = 0
        self.awaited_path: Optional[MapPath] = None

        self.max_speed = 0
        self.current_speed = 0
        self.rotation_speed = 0

        self.permanent_units_group: int = 0
        self.navigating_group = None
        self.waypoints_queue = None

        self.tasks = []

        self.outside = True

        self.explosion_name = EXPLOSION

        self.layered_spritelist.swap_rendering_layers(self, 0, self.current_node.grid[1])

    @abstractmethod
    def _load_textures(self):
        """
        Since we can have many spritesheets representing our Unit.
        Some units have rotating turrets, so above the normal 8-texture
        spritesheets, they require 8 textures for each hull direction x8
        turret directions, what makes 8x8 spritesheet, whereas other Units
        use single row 8-texture spritesheet.
        """
        raise NotImplementedError

    def angle_to_texture(self, angle_to_target: float):
        """
        Our units can face only 16 possible angles, which are precalculated
        for each one of 360 possible integer angles for fast lookup in existing
        angles-dict.
        """
        self.facing_direction = index = self.angles[int(angle_to_target)]
        self.set_texture(index)

    @property
    def adjacent_nodes(self) -> List[MapNode]:
        return self.current_node.adjacent_nodes

    @property
    def is_moving(self) -> bool:
        return bool(self.change_x or self.change_y)

    def reached_destination(self, destination: Union[MapNode, GridPosition]) -> bool:
        try:
            return destination.grid == self.current_node.grid
        except AttributeError:
            return destination == self.current_node.grid

    def is_heading_to(self, destination: Union[MapNode, GridPosition]):
        return self.path and self.path[-1] == map_grid_to_position(destination)

    def on_mouse_enter(self):
        if self.selection_marker is None:
            self.game.units_manager.create_units_selection_markers((self,))

    def on_mouse_exit(self):
        if self.selection_marker is not None and not self.is_selected:
            self.game.units_manager.remove_from_selection_markers(self.selection_marker)

    @property
    def is_selected(self) -> bool:
        selected = self in self.game.units_manager.selected_units
        if (selection := self.game.mouse.mouse_drag_selection) is None:
            return selected
        return selected or self in selection

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        new_current_node = self.update_current_node()
        self.update_observed_area(new_current_node)
        self.update_blocked_map_nodes(new_current_node)
        self.update_pathfinding()

    def update_current_node(self):
        current_node = self.get_current_node()
        if current_node is not self.current_node:
            if self.quadtree is not None and not self.quadtree.in_bounds(self):
                self.update_in_map_quadtree()
        return current_node

    def get_current_node(self):
        current_node = self.map.position_to_node(*self.position)
        if (old_y := self.current_node.grid[1]) != (new_y := current_node.grid[1]):
            self.layered_spritelist.swap_rendering_layers(self, old_y, new_y)
        return current_node

    def update_observed_area(self, current_node: MapNode):
        if self.observed_nodes and current_node == self.current_node:
            pass
        else:
            self.observed_grids = grids = self.calculate_observed_area()
            self.observed_nodes = {self.map[grid] for grid in grids}

    def update_blocked_map_nodes(self, new_current_node: MapNode):
        """
        Units are blocking MapNodes they are occupying to enable other units
        avoid collisions by navigating around blocked nodes.
        """
        if self.path:
            self.scan_next_nodes_for_collisions()
        self.update_current_blocked_node(new_current_node)
        if len(self.path) > 1:
            self.update_reserved_node()

    def update_current_blocked_node(self, new_current_node: MapNode):
        self.swap_blocked_nodes(self.current_node, new_current_node)
        self.current_node = new_current_node

    def update_reserved_node(self):
        new_reserved_node = self.map.position_to_node(*self.path[0])
        self.swap_blocked_nodes(self.reserved_node, new_reserved_node)
        self.reserved_node = new_reserved_node

    def swap_blocked_nodes(self, unblocked: MapNode, blocked: MapNode):
        if unblocked is not None:
            self.unblock_map_node(unblocked)
        self.block_map_node(blocked)

    @staticmethod
    def unblock_map_node(node: MapNode):
        node.unit = None

    def block_map_node(self, node: MapNode):
        node.unit = self

    def scan_next_nodes_for_collisions(self):
        next_node = self.map.position_to_node(*self.path[0])
        if next_node.unit not in (self, None):
            self.find_best_way_to_avoid_collision(next_node.unit)
        elif next_node.static_gameobject is not None:
            self.find_alternative_path()

    def find_best_way_to_avoid_collision(self, blocker: Unit):
        if blocker.has_destination or self.is_enemy(blocker):
            self.wait_for_free_path(self.path)
        elif self.find_alternative_path() is not None:
            pass
        else:
            self.ask_for_pass(blocker)

    @property
    def has_destination(self) -> bool:
        return self.path or self.awaited_path or self in Pathfinder.instance

    def wait_for_free_path(self, path: Deque):
        """
        Waiting for free path is useful when next node is only temporarily
        blocked (blocking Unit is moving) and allows to avoid pathfinding
        the path with A* algorithm. Instead, Unit 'shelves' currently found
        path and after 1 second 'unshelves' it in countdown_waiting method.
        """
        self.path_wait_counter = time.time() + 1
        self.awaited_path = path.copy()
        self.path.clear()
        self.stop()

    def find_alternative_path(self) -> Optional[Deque]:
        if len(path := self.path) > 1:
            destination = self.map.position_to_node(*path[1])
            adjacent = self.current_node.walkable_adjacent
            for node in (n for n in adjacent if n in destination.walkable_adjacent):
                self.path[0] = node.position
                return self.path

    def ask_for_pass(self, blocker: Unit):
        if blocker.find_free_tile_to_unblock_way(self.path):
            self.wait_for_free_path(self.path)
        else:
            destination = position_to_map_grid(*self.path[-1])
            self.move_to(destination)

    def find_free_tile_to_unblock_way(self, path) -> bool:
        if adjacent := self.current_node.walkable_adjacent:
            free_tile = random.choice([node for node in adjacent])
            self.move_to(free_tile.grid)
            return True
        return False

    def update_pathfinding(self):
        if self.awaited_path is not None:
            self.countdown_waiting(self.awaited_path)
        elif self.path:
            self.follow_path()
        else:
            self.stop()

    def countdown_waiting(self, path):
        if time.time() >= self.path_wait_counter:
            node = self.map.position_to_node(*path[0])
            if node.is_walkable or len(path) < 20:
                self.restart_path(path)
            else:
                self.path_wait_counter += 1

    def restart_path(self, path):
        if len(path) > 20:
            self.path = deque(path)
        else:
            x, y = path[-1]
            self.move_to(position_to_map_grid(x, y), self.forced_destination)
        self.awaited_path = None

    def follow_path(self):
        destination = self.path[0]
        if dist(self.position, destination) < CLOSE_ENOUGH_DISTANCE * self.max_speed:
            self.move_to_next_waypoint()
        else:
            angle_to_target = int(calculate_angle(*self.position, *destination))
            if self.virtual_angle != angle_to_target:
                self.stop()
                return self.rotate_towards_target(angle_to_target)
            self.move_to_current_waypoint(destination)

    def rotate_towards_target(self, angle_to_target):
        """
        Virtually Rotate Unit sprite before it starts movement toward its
        current destination. We do not rotate actual Sprite, but change the
        current sprite-sheet index to display correct image of unit rotated \
        the correct direction.
        """
        self.virtual_angle = self.calculate_virtual_angle(angle_to_target)
        self.set_rotated_texture()

    def calculate_virtual_angle(self, angle_to_target) -> int:
        angular_difference = abs(self.virtual_angle - angle_to_target)
        rotation = min(angular_difference, self.rotation_speed)
        if angular_difference < 180:
            direction = 1 if self.virtual_angle < angle_to_target else -1
        else:
            direction = -1 if self.virtual_angle < angle_to_target else 1
        return int((self.virtual_angle + (rotation * direction)) % 360)

    def set_rotated_texture(self):
        self.angle_to_texture(self.virtual_angle)

    def move_to_next_waypoint(self):
        self.path.popleft()

    def move_to_current_waypoint(self, destination):
        angle = calculate_angle(*self.position, *destination)
        self.change_x, self.change_y = vector_2d(angle, self.max_speed * self.health_ratio)

    def move_to(self, destination: GridPosition, forced: bool = False):
        self.cancel_path_requests()
        self.forced_destination = forced
        start = position_to_map_grid(*self.position)
        self.game.pathfinder.request_path(self, start, destination)

    def follow_new_path(self, new_path: MapPath):
        self.path.clear()
        self.awaited_path = None
        self.path.extend(new_path[1:])
        self.unschedule_earlier_move_orders()

    def unschedule_earlier_move_orders(self):
        for event in (e for e in self.scheduled_events if e.function == self.move_to):
            self.unschedule_event(event)

    def cancel_path_requests(self):
        self.game.pathfinder.cancel_unit_path_requests(unit=self)

    def stop_completely(self):
        self.set_navigating_group(navigating_group=None)
        self.forced_destination = False
        self.leave_waypoints_queue()
        self.cancel_path_requests()
        self.awaited_path = None
        self.path.clear()
        self.cancel_tasks()

    def leave_waypoints_queue(self):
        self.game.pathfinder.remove_unit_from_waypoint_queue(unit=self)

    def set_permanent_units_group(self, index: int = 0):
        if (cur_index := self.permanent_units_group) and cur_index != index:
            try:
                self.game.units_manager.permanent_units_groups[cur_index].discard(self)
            except KeyError:
                log_here(f'Unable to remove Unit from permanent groups due to KeyError: {cur_index}.')
        self.permanent_units_group = index

    def update_battle_behaviour(self):
        if not self.weapons or not self.ammunition:
            return self.run_away()
        if (enemy := self._enemy_assigned_by_player) is not None:
            self.handle_enemy(enemy)
        if (enemy := self.targeted_enemy or self.select_enemy_from_known_enemies()) is not None:
            self.targeted_enemy = enemy
            self.handle_enemy(enemy)

    def handle_enemy(self, enemy: PlayerEntity):
        assigned = enemy is self._enemy_assigned_by_player
        if self.in_attack_range(enemy):
            if assigned or (self._enemy_assigned_by_player is None and not self.forced_destination):
                self.stop_completely()
            self.fight_enemy(enemy)
        elif (assigned or self._enemy_assigned_by_player is None) and not self.forced_destination:
            self.move_toward_enemy(enemy)

    def move_toward_enemy(self, enemy: PlayerEntity):
        if not (enemy is self._enemy_assigned_by_player or self.has_destination):
            self.game.pathfinder.navigate_units_to_destination([self], *enemy.position)

    def run_away(self):
        pass

    def fight_enemy(self, enemy):
        if enemy.is_alive and enemy.is_enemy(self):
            self.attack(enemy)
        elif self._enemy_assigned_by_player is enemy:
            self._enemy_assigned_by_player = self.targeted_enemy = None
        else:
            self.targeted_enemy = None

    def kill(self):
        self.assign_enemy(None)
        self.stop_completely()
        self.set_permanent_units_group()
        self.clear_all_blocked_nodes()
        self.animate_and_communicate_unit_death()
        super().kill()

    @ignore_in_editor_mode
    def animate_and_communicate_unit_death(self):
        if self.outside and self.is_rendered:
            self.create_death_animation()
        if self.player.is_human_player:
            self.game.sound_player.play_sound('unit_lost.vaw')

    def cancel_tasks(self):
        for task in self.tasks:
            task.remove(self)
        self.tasks.clear()

    def set_navigating_group(self, navigating_group):
        if self.navigating_group is not None:
            self.navigating_group.discard(self)
        self.navigating_group = navigating_group

    def clear_all_blocked_nodes(self):
        for node in (self.current_node, self.reserved_node):
            self.unblock_map_node(node) if node is not None else ...

    def create_death_animation(self):
        if not self.is_infantry:  # particular Soldiers dying instead
            self.game.create_effect(Explosion, 'EXPLOSION', *self.position)

    def save(self) -> Dict:
        saved_unit = super().save()
        saved_unit.update(
            {
                'path': [p for p in self.path],
                'path_wait_counter': self.path_wait_counter,
                'awaited_path': self.awaited_path,
                'permanent_units_group': self.permanent_units_group
            }
        )
        return saved_unit

    def after_respawn(self, loaded_data: Dict):
        super().after_respawn(loaded_data)
        self.path = deque(loaded_data['path'])

    def create_ui_information_about_unit(self, x, y) -> list[UiElement]:
        health_color = value_to_color(self.health, self.max_health)
        ammo_color = value_to_color(self.ammunition, self.max_ammunition)
        info = [
            UiTextLabel(x, y + 20, self.localize(self.object_name.upper()), 15, GREEN, 'unit name', active=False),
            UiTextLabel(x, y -5, f'HP: {int(self.health)}/{self.max_health}', 12, health_color, 'health', active=False),
        ]
        if self.weapons:
            info.append(UiTextLabel(x, y - 55, f'{self.localize("AMMUNITION")}: {self.ammunition}/{self.max_ammunition}',
                                            12, ammo_color, 'ammunition', active=False))
        if self.is_controlled_by_human_player:
            info.append(UiTextLabel(x, y - 80, f'{self.localize("EXPERIENCE")}: {self.experience}', 12, GREEN,
                                            'experience', active=False))
        return info

    def update_ui_information_about_unit(self):
        selected_units_bundle = self.game.get_bundle(UI_UNITS_PANEL)
        for attribute in ('health', 'fuel', 'ammunition', 'experience'):
            try:
                value = getattr(self, attribute)
                max_value = getattr(self, f'max_{attribute}')
                info_label = selected_units_bundle.find_by_name(attribute)
                info_label.text = f'{self.localize(attribute.upper())}: {int(value)} / {max_value}'
                info_label.text_color = value_to_color(value, max_value)
            except AttributeError:
                continue

    def create_actions_buttons_specific_for_this_unit(self, x, y) -> List[UiElement]:
        ...


class Vehicle(Unit):
    """An interface for all Units which are engine-powered vehicles."""
    allowed_terrains = TerrainType.GROUND

    def __init__(self, texture_name: str, player: Player, weight: int,
                 position: Point, object_id: int = None):
        super().__init__(texture_name, player, weight, position, object_id)

        self._load_textures()
        self.hit_box = self.texture.hit_box_points

        thread_texture = f'{self.object_name}_threads.png'
        # texture of the VehicleThreads left by this Vehicle
        self.threads_texture = self.game.resources_manager.get(thread_texture)
        # when this Vehicle left its threads on the ground last time:
        self.threads_time = 0

        self.max_fuel = self.fuel = self.configs['fuel']
        self.fuel_consumption = self.configs['fuel_consumption']

    @cached_property
    def threads_frequency(self):
        return 200 / self.max_speed

    def _load_textures(self):
        width, height = get_texture_size(self.full_name, columns=ROTATIONS)
        self.textures = load_textures(
            self.filename_with_path,
            [(i * width, 0, width, height) for i in range(ROTATIONS)]
        )
        # TODO: change 'textures' for Vehicle to 2d list to show: 1. current_activity, and 2. facing_direction
        self.set_texture(self.facing_direction)

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        if self.is_moving:
            self.consume_fuel()
            if self.is_rendered and self.game.settings.vehicles_threads and self.threads_texture is not None:
                self.leave_threads()

    def consume_fuel(self):
        self.fuel -= self.fuel_consumption

    def leave_threads(self):
        if (t := self.timer.frames) - self.threads_time >= self.threads_frequency:
            self.threads_time = t
            self.game.vehicles_threads.append(VehicleThreads(self.threads_texture, self.facing_direction, *self.position))

    @ignore_in_editor_mode
    def animate_and_communicate_unit_death(self):
        super().animate_and_communicate_unit_death()
        self.spawn_wreck()

    def spawn_wreck(self):
        self.game.spawn(f'{self.object_name}_wreck.png', None, self.position, self.facing_direction)

    def create_ui_information_about_unit(self, x, y) -> list[UiElement]:
        return super().create_ui_information_about_unit(x, y) + [
            UiTextLabel(x, y - 30, f'{self.localize("FUEL")}: {int(self.fuel)}/{self.max_fuel}',
                        12, value_to_color(self.fuel, self.max_fuel), 'fuel', active=False),
        ]


class VehicleThreads(Sprite):
    """Creates a VehicleThreads sprite."""

    def __init__(self, texture, index, x, y):
        super().__init__(texture, center_x=x, center_y=y, hit_box_algorithm='None')
        self.texture = load_texture(texture, index * 80, 0, 80, 21)

    def on_update(self, delta_time: float = 1 / 60):
        # threads slowly disappearing through time
        if self.alpha:
            self.alpha -= 1
        else:
            self.kill()


class VehicleWithTurret(Vehicle):
    """An interface for all Units which are engine-powered vehicles, and which have a turret."""

    def __init__(self, texture_name: str, player: Player, weight: int,
                 position: Point, object_id: int = None):
        # combine facing_direction with turret to obtain proper texture:
        self.turret_facing_direction = random.randint(0, ROTATIONS - 1)
        super().__init__(texture_name, player, weight, position, object_id)
        self.turret_aim_target = None

    def _load_textures(self):
        """
        Create 16 lists of 16-texture spritesheets for each combination of hull
        and turret directions possible in game.
        """
        width, height = get_texture_size(self.full_name, ROTATIONS, ROTATIONS)
        self.textures = [load_textures(self.filename_with_path,
            [(i * width, j * height, width, height) for i in range(ROTATIONS)]) for j in range(ROTATIONS)
        ]
        # TODO: change 'textures' for Vehicle to 3d list to show:
        #  1. current_activity,
        #  2. facing_direction,
        #  3. turret_facing_direction
        self.set_texture(self.facing_direction, self.turret_facing_direction)

    def set_rotated_texture(self):
        if (enemy := self.turret_aim_target) is not None:
            self.set_hull_and_turret_texture(enemy)
        else:
            self.angle_to_texture(hull_angle=self.virtual_angle)

    def set_hull_and_turret_texture(self, enemy):
        turret_angle = calculate_angle(*self.position, *enemy.position)
        self.angle_to_texture(self.virtual_angle, turret_angle)

    def angle_to_texture(self,
                         hull_angle: float = None,
                         turret_angle: float = None):
        if hull_angle is not None:
            self.facing_direction = self.angles[int(hull_angle)]
        # in case of VehicleWithTurret we need to set its turret direction too:
        if turret_angle is None:
            self.turret_facing_direction = self.facing_direction
        else:
            self.turret_facing_direction = self.angles[int(turret_angle)]
        self.set_texture(self.facing_direction, self.turret_facing_direction)

    def set_texture(self, hull_texture_index: int, turret_texture_index: int):
        """
        We override original method to work with 2 texture indexes combined:
        first for the hull (which list of textures to use) and second for
        turret for actual texture to be chosen from the list.
        """
        if (texture := self.textures[hull_texture_index][turret_texture_index]) == self._texture:
            return
        self.clear_spatial_hashes()
        self._point_list_cache = None
        self._texture = texture
        self._width = texture.width * self.scale
        self._height = texture.height * self.scale
        self.add_spatial_hashes()
        for sprite_list in self.sprite_lists:
            sprite_list.update_texture(self)

    def on_update(self,delta_time: float = 1/60):
        self.turret_aim_target = None
        super().on_update(delta_time)

    def fight_enemy(self, enemy: PlayerEntity):
        self.turret_aim_target = enemy
        self.set_hull_and_turret_texture(enemy)
        super().fight_enemy(enemy)

    def spawn_wreck(self):
        self.game.spawn(f'{self.object_name}_wreck.png', None, self.position, (self.facing_direction, self.turret_facing_direction))


class Boat(Vehicle):
    allowed_terrains = TerrainType.WATER


class BoatWithTurret(Boat):
    ...


class AirUnit(Vehicle):
    allowed_terrains = TerrainType.WATER

    def __init__(self, texture_name: str, player: Player, weight: int, position: Point):
        super().__init__(texture_name, player, weight, position)

        # AirUnits cast shadows on the ground at the position under theirs own position
        self.shadow: Optional[Shadow] = None

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        self.shadow.on_update(delta_time)


class Shadow(Sprite):
    ...


class Soldier(Unit):
    allowed_terrains = TerrainType.GROUND
    health_restoration = 0.003
    infantry_steps_duration = 0.05

    def __init__(self, texture_name: str, player: Player, weight: int,
                 position: Point, object_id: Optional[int] = None):
        super().__init__(texture_name, player, weight, position, object_id)
        self.last_step_time = 0
        self.activity = UnitActivity.IDLE
        self.outside = True
        self.equipment = None
        self.all_textures: Dict[int, List[List[Texture]]] = {}
        self._load_textures()

    def _load_textures(self):
        texture_name = get_path_to_file(self.full_name)
        width, height = get_texture_size(self.full_name, rows=ROTATIONS, columns=ROTATIONS)

        self.all_textures = {
            stance: self.load_pose_textures(texture_name, width, height, stance)
            for stance in (UnitActivity.IDLE,)  # TODO: MOVE, CRAWL
        }

        self.textures = self.all_textures[self.activity][self.facing_direction]
        self.set_texture(0)
        self.hit_box = self.texture.hit_box_points

    @staticmethod
    def load_pose_textures(texture_name, width, height, stance):
        start = ROTATIONS * stance
        return [
            load_textures(
                texture_name, [(i * width, j * height, width, height)
                               for i in range(ROTATIONS)]
            ) for j in range(start, start + ROTATIONS)
        ]

    @property
    def should_be_rendered(self) -> bool:
        return self.outside and super().should_be_rendered

    @property
    def is_controlled_by_human_player(self) -> bool:
        return self.player.is_human_player and self.is_rendered  # selecting Soldiers in Buildings is forbidden

    def on_update(self, delta_time=1/60):
        super().on_update(delta_time)
        if self.on_screen and self.is_moving:
            self.update_animation(delta_time)

    def angle_to_texture(self, angle_to_target: float):
        index = self.angles[int(angle_to_target)]
        self.textures = self.all_textures[self.activity][index]

    def update_animation(self, delta_time: float = 1/60):
        self.last_step_time += delta_time
        if self.last_step_time > self.infantry_steps_duration:
            self.last_step_time = 0
            if self.cur_texture_index < ROTATIONS - 1:
                self.cur_texture_index += 1
            else:
                self.cur_texture_index = 0
            self.set_texture(self.cur_texture_index)

    def enter_building(self, building):
        self.outside = False
        self.stop_completely()
        self.assign_enemy(None)
        if self in self.game.units_manager:
            self.game.units_manager.unselect(self)
        self.stop_rendering()
        self.stop_updating()
        building.on_soldier_enter(soldier=self)

    def leave_building(self, building):
        x, y = building.position  # TODO: replace this with Building exit position
        self.position = self.game.pathfinder.get_closest_walkable_position(x, y)
        self.insert_to_map_quadtree()
        self.outside = True
        self.start_rendering()
        self.start_updating()

    def restore_health(self):
        wounds = round(self._max_health - self.health, 3)
        health_gained = min(self.health_restoration, wounds)
        self.health += health_gained

    def create_death_animation(self):
        self.spawn_corpse()

    def spawn_corpse(self):
        corpse_name = self.colored_name + "_corpse.png"
        self.game.spawn(corpse_name, None, self.position, self.facing_direction)


class Engineer(Soldier):

    @classmethod
    def create_ui_buttons(cls, x, y):
        pass


class UnitsOrderedDestinations:
    """
    When Player sends his Units somewhere on the map by mouse-clicking there,
    this class stores all positions each Unit was assigned as it's final
    destination by the Pathfinder. It also keeps all WaypointsQueues.
    Game uses these positions to display on the ordered destinations on the
    screen for the Player convenience.
    """
    size = 1

    def __init__(self):
        self.destinations = []
        self.waypoints_queues = []
        self.seconds_left = 0

    def new_destinations(self, destinations: List[Point], units: List[Unit]):
        self.seconds_left = 3
        self.destinations = [[x, y, self.size, GREEN, 4, unit] for ((x, y), unit) in zip(destinations, units)]

    def new_waypoints_queue(self, queue):
        self.waypoints_queues.append(queue)

    def remove_queue(self, queue):
        self.waypoints_queues.remove(queue)

    def on_update(self, delta_time):
        self.update_destinations(delta_time)
        self.update_waypoints_queues()

    def update_destinations(self, delta_time):
        if self.seconds_left > 0:
            self.seconds_left -= delta_time
            for destination in self.destinations:
                destination[2] = self.size * self.seconds_left
        else:
            self.destinations.clear()

    def update_waypoints_queues(self):
        ...

    def draw(self):
        self.draw_destinations()
        self.draw_waypoints_queues()

    def draw_destinations(self):
        for destination in self.destinations:
            draw_circle_filled(*destination[:-1])
            x1, y1 = destination[:2]
            x2, y2 = destination[-1].position
            draw_line(x1, y1, x2, y2, GREEN)

    def draw_waypoints_queues(self):
        for queue in self.waypoints_queues:
            if queue.visible:
                self.draw_waypoints(queue.waypoints)

    @staticmethod
    def draw_waypoints(waypoints):
        px, py = None, None
        for i, waypoint in enumerate(waypoints, start=1):
            x, y = waypoint
            draw_circle_outline(x, y, 20, GREEN)
            draw_text(str(i), x, y, GREEN, font_size=20, anchor_x='center', anchor_y='center')
            if px is not None:
                draw_line(px, py, x, y, GREEN)
            px, py = x, y
