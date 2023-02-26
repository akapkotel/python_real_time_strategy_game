#!/usr/bin/env python
from __future__ import annotations

import random
import time

from math import dist
from abc import abstractmethod
from collections import deque
from functools import cached_property
from typing import Deque, List, Dict, Optional, Union

from arcade import Sprite, load_textures, draw_circle_filled, Texture, draw_text
from arcade.arcade_types import Point

from effects.constants import SHOT_BLAST, EXPLOSION
from effects.explosions import Explosion
from map.map import (
    GridPosition, MapNode, MapPath, Pathfinder, Sector, normalize_position,
    position_to_map_grid
)
from players_and_factions.player import Player, PlayerEntity
from utils.colors import GREEN
from utils.functions import (get_path_to_file, get_texture_size, ignore_in_editor_mode)
from utils.geometry import (
    precalculate_possible_sprites_angles, calculate_angle,
    vector_2d, ROTATION_STEP, ROTATIONS, find_area
)
from units.weapons import Weapon

INFANTRY_STEPS_SPEED = 0.05


class Unit(PlayerEntity):
    """
    Unit is a PlayerEntity which can move on map.
    """
    angles = precalculate_possible_sprites_angles()

    def __init__(self,
                 unit_name: str,
                 player: Player,
                 weight: int,
                 position: Point,
                 id: Optional[int] = None):
        PlayerEntity.__init__(self, unit_name, player, position, id=id)
        # Since we do not rotate actual Sprite, but change it's texture to show
        # the correctly rotated Units on the screen, use 'virtual' rotation to
        # keep track of the Unit rotation angle without rotating actual Sprite:
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

        self._weapons.extend(
            Weapon(name=name, owner=self) for name in
            self.configs['weapons_names']
        )

        self.tasks = []
        self.current_task = None

        self.outside = True

        self.explosion_name = EXPLOSION
        self.update_explosions_pool()

        self.layered_spritelist.swap_rendering_layers(self, 0, self.current_node.grid[1])

    @property
    def configs(self):
        return self.game.configs['units'][self.object_name]

    def update_explosions_pool(self):
        """
        Assure that there would be enough Explosion instances in the pool to
        get one when this Unit is destroyed.
        """
        name = self.explosion_name
        required = len([u for u in self.game.units if u.explosion_name == name])
        self.game.explosions_pool.add(SHOT_BLAST, required)
        self.game.explosions_pool.add(name, required)

    @abstractmethod
    def _load_textures_and_reset_hitbox(self):
        """
        Since we can have many different spritesheets representing our Unit.
        Some units have rotating turrets, so above the normal 8-texture
        spritesheets, they require 8 textures for each hull direction x8
        turret directions, what makes 8x8 spritesheet, whereas other Units
        use single row 8-texture spritesheet.
        """
        raise NotImplementedError

    def angle_to_texture(self, angle_to_target: float):
        """
        Our units can face only 8 possible angles, which are precalculated
        for each one of 360 possible integer angles for fast lookup in existing
        angles-dict.
        """
        index = self.angles[int(angle_to_target)]
        self.set_texture(index)

    @property
    def adjacent_nodes(self) -> List[MapNode]:
        return self.current_node.adjacent_nodes

    @property
    def moving(self) -> float:
        return self.change_x or self.change_y

    def reached_destination(self, destination: Union[MapNode, GridPosition]) -> bool:
        try:
            return destination.grid == self.current_node.grid
        except AttributeError:
            return destination == self.current_node.grid

    def heading_to(self, destination: Union[MapNode, GridPosition]):
        return self.path and self.path[0] == self.map.map_grid_to_position(destination)

    def on_mouse_enter(self):
        if self.selection_marker is None:
            self.game.units_manager.create_units_selection_markers((self,))

    def on_mouse_exit(self):
        if self.selection_marker is not None and not self.is_selected:
            self.game.units_manager.remove_from_selection_markers(entity=self)

    @property
    def is_selected(self) -> bool:
        selected = self in self.game.units_manager.selected_units
        if (selection := self.game.cursor.mouse_drag_selection) is None:
            return selected
        return selected or self in selection

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        new_current_node = self.update_current_node()
        self.update_observed_area(new_current_node)
        self.update_blocked_map_nodes(new_current_node)
        self.update_pathfinding()

    def draw(self):
        # draw_text(f'{self.id};{self._enemy_assigned_by_player is not None};'
        #           f'{self.targeted_enemy is not None}',
        #           self.right, self.bottom, (255, 255, 255), 14)
        super().draw()

    def update_current_node(self):
        current_node = self.get_current_node()
        if current_node is not self.current_node:
            if dist(self.position, self.quadtree.position) > self.quadtree.smaller_dimension:
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

    def update_fire_covered_area(self):
        area = find_area(*self.current_node.grid, self.attack_range_matrix)
        self.fire_covered = {self.map[g] for g in self.map.in_bounds(area)}

    def update_blocked_map_nodes(self, new_current_node: MapNode):
        """
        Units are blocking MapNodes they are occupying to enable other units
        avoid collisions by navigating around blocked nodes.
        """
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
        if self.path:
            next_node = self.map.position_to_node(*self.path[0])
            if next_node.unit not in (self, None):
                self.find_best_way_to_avoid_collision(next_node.unit)

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
            if node.walkable or len(path) < 20:
                self.restart_path(path)
            else:
                self.path_wait_counter += 1

    def restart_path(self, path):
        if len(path) > 20:
            self.path = deque(path)
        else:
            destination_position = path[-1]
            self.move_to(position_to_map_grid(*destination_position))
        self.awaited_path = None

    def follow_path(self):
        destination = self.path[0]

        angle_to_target = int(calculate_angle(*self.position, *destination))
        if self.virtual_angle != angle_to_target:
            self.stop()
            return self.rotate_towards_target(angle_to_target)

        speed = self.current_speed
        if (distance_left := dist(self.position, destination)) <= speed:
            self.move_to_next_waypoint()
        else:
            self.move_to_current_waypoint(destination, distance_left)

    def rotate_towards_target(self, angle_to_target):
        """
        Virtually Rotate Unit sprite before it starts movement toward it's
        current destination. We do not rotate actual Sprite, but change the
        current sprite-sheet index to display correct image of unit rotated \
        the correct direction.
        """
        self.calculate_unit_virtual_angle(angle_to_target)
        self.set_rotated_texture()

    def calculate_unit_virtual_angle(self, angle_to_target):
        difference = abs(self.virtual_angle - angle_to_target)
        rotation = min(difference, self.rotation_speed)
        if difference < 180:
            direction = 1 if self.virtual_angle < angle_to_target else -1
        else:
            direction = -1 if self.virtual_angle < angle_to_target else 1
        self.virtual_angle = (self.virtual_angle + (rotation * direction)) % 360

    def set_rotated_texture(self):
        self.angle_to_texture(self.virtual_angle)

    def move_to_next_waypoint(self):
        self.path.popleft()

    def move_to_current_waypoint(self, destination, distance_left):
        angle = calculate_angle(*self.position, *destination)
        self.current_speed = speed = min(distance_left, self.max_speed)
        self.change_x, self.change_y = vector_2d(angle, speed)

    def move_to(self, destination: GridPosition, force_destination=True):
        self.cancel_path_requests()
        self.forced_destination = force_destination
        start = position_to_map_grid(*self.position)
        self.game.pathfinder.request_path(self, start, destination)

    def follow_new_path(self, new_path: MapPath):
        self.path.clear()
        self.awaited_path = None
        self.path.extend(new_path[1:])
        self.forced_destination = True
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
                pass
        self.permanent_units_group = index

    @ignore_in_editor_mode
    def update_battle_behaviour(self):
        in_range = self.in_attack_range
        for enemy in (self._enemy_assigned_by_player, self.select_enemy_from_known_enemies()):
            if enemy is not None:
                if in_range(enemy):
                    self._targeted_enemy = enemy
                    self.fight_enemy(enemy)

    def move_toward_enemy(self, enemy: PlayerEntity):
        self.move_to(position_to_map_grid(*enemy.position), False)

    def run_away(self):
        pass

    def fight_enemy(self, enemy):
        if enemy.alive:
            self.attack(enemy)
        else:
            if self._enemy_assigned_by_player is enemy:
                self._enemy_assigned_by_player = None
            self.targeted_enemy = None

    def consume_ammunition(self, amount: float):
        self._ammunition = max(0, self._ammunition - amount)

    def kill(self):
        self.stop_completely()
        self.game.units_manager.unselect(self)
        self.set_permanent_units_group()
        self.clear_all_blocked_nodes()
        if self.outside:
            self.create_death_animation()
        super().kill()

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
            # self.game.window.sound_player.play_sound('explosion.wav')

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


class Vehicle(Unit):
    """An interface for all Units which are engine-powered vehicles."""

    def __init__(self, texture_name: str, player: Player, weight: int,
                 position: Point, id: int = None):
        super().__init__(texture_name, player, weight, position, id)
        thread_texture = ''.join((self.object_name, '_threads.png'))

        # texture of the VehicleThreads left by this Vehicle
        self.threads_texture = get_path_to_file(thread_texture)
        # when this Vehicle left it's threads on the ground last time:
        self.threads_time = 0

        self.fuel = 100.0
        self.fuel_consumption = 0.0

    @cached_property
    def threads_frequency(self):
        return 5 / self.max_speed

    def _load_textures_and_reset_hitbox(self):
        width, height = get_texture_size(self.full_name, columns=8)
        self.textures = load_textures(
            get_path_to_file(self.filename_with_path),
            [(i * width, 0, width, height) for i in range(8)]
        )

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        if self.moving:
            self.consume_fuel()
            if self.is_rendered and self.game.settings.vehicles_threads:
                self.leave_threads()

    def consume_fuel(self):
        self.fuel -= self.fuel_consumption

    def leave_threads(self):
        if (t := self.timer['f']) - self.threads_time >= self.threads_frequency:
            self.threads_time = t
            self.game.vehicles_threads.append(self.create_threads())

    def create_threads(self):
        return VehicleThreads(self.threads_texture, self.cur_texture_index, *self.position),

    def kill(self):
        self.spawn_wreck()
        super().kill()

    def spawn_wreck(self):
        wreck_name = f'{self.object_name.rstrip(".png")}_wreck.png'
        self.game.spawn(wreck_name, self.position, self.cur_texture_index)


class VehicleThreads(Sprite):

    __slots__ = ['textures']

    def __init__(self, texture, index, x, y):
        super().__init__(texture, center_x=x, center_y=y, hit_box_algorithm='None')
        self.textures = load_textures(
            texture, [(i * 29, 0, 29, 28) for i in range(8)]
        )
        self.set_texture(index)

    def on_update(self, delta_time: float = 1 / 60):
        # threads slowly disappearing through time
        if self.alpha > 1:
            self.alpha -= 1
        else:
            self.kill()


class Tank(Vehicle):

    def __init__(self, texture_name: str, player: Player, weight: int,
                 position: Point, id: int = None):
        super().__init__(texture_name, player, weight, position, id)

        # combine facing_direction with turret to obtain proper texture:
        self.turret_facing_direction = random.randint(0, ROTATIONS - 1)

        self._load_textures_and_reset_hitbox()
        self.turret_aim_target = None
        self.barrel_end = self.turret_facing_direction

    def _load_textures_and_reset_hitbox(self):
        """
        Create 8 lists of 8-texture spritesheets for each combination of hull
        and turret directions.
        """
        width, height = get_texture_size(self.full_name, 8, 8)
        self.textures = [load_textures(self.filename_with_path,
            [(i * width, j * height, width, height) for i in range(8)]) for j in range(8)
        ]
        self.set_texture(self.facing_direction, self.turret_facing_direction)
        self.set_hit_box(self.texture.hit_box_points)

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
        # for Tank we need to set it's turret direction too:
        if turret_angle is None:
            self.turret_facing_direction = self.facing_direction
        else:
            self.turret_facing_direction = self.angles[int(turret_angle)]
        self.barrel_end = self.turret_facing_direction
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

    def on_update(self, delta_time: float = 1/60):
        self.turret_aim_target = None
        super().on_update(delta_time)

    def create_threads(self):
        return VehicleThreads(self.threads_texture, self.facing_direction, *self.position)

    def fight_enemy(self, enemy: PlayerEntity):
        self.turret_aim_target = enemy
        self.set_hull_and_turret_texture(enemy)
        super().fight_enemy(enemy)

    def spawn_wreck(self):
        wreck_name = f'{self.object_name}_wreck.png'
        self.game.spawner.spawn(
            wreck_name, None, self.position,
            (self.facing_direction, self.turret_facing_direction)
        )


IDLE = 0
MOVE = 1
KNEEL = 2
CRAWL = 3


class Soldier(Unit):
    health_restoration = 0.003

    def __init__(self, texture_name: str, player: Player, weight: int,
                 position: Point, id: Optional[int] = None):
        super().__init__(texture_name, player, weight, position, id)
        self.last_step = 0
        self.stance = IDLE
        self.all_textures: Dict[int, List[List[Texture]]] = {}
        self._load_textures_and_reset_hitbox()

        self.equipment = None

        self.outside = True

    def _load_textures_and_reset_hitbox(self):
        texture_name = get_path_to_file(self.full_name)
        width, height = get_texture_size(self.full_name, rows=9, columns=8)

        self.all_textures = {
            stance: self.load_pose_textures(texture_name, width, height, stance)
            for stance in (IDLE,)  # MOVE, KNEEL, CRAWL
        }

        self.textures = self.all_textures[self.stance][self.facing_direction]
        self.set_texture(0)
        self.set_hit_box(self.texture.hit_box_points)

    @staticmethod
    def load_pose_textures(texture_name, width, height, stance):
        start = 8 * stance
        return [
            load_textures(
                texture_name, [(i * width, j * height, width, height)
                               for i in range(8)]
            ) for j in range(start, start + 8)
        ]

    @property
    def should_be_rendered(self) -> bool:
        return self.on_screen and self.outside

    @property
    def selectable(self) -> bool:
        return self.player.is_local_human_player and self.outside

    def on_update(self, delta_time=1/60):
        if self.outside:
            super().on_update(delta_time)
        if self.on_screen and self.moving:
            self.update_animation(delta_time)

    def angle_to_texture(self, angle_to_target: float):
        index = self.angles[int(angle_to_target)]
        self.textures = self.all_textures[self.stance][index]

    def update_animation(self, delta_time: float = 1/60):
        self.last_step += delta_time
        if self.last_step > INFANTRY_STEPS_SPEED:
            self.last_step = 0
            if self.cur_texture_index < len(self.textures) - 1:
                self.cur_texture_index += 1
            else:
                self.cur_texture_index = 0
            self.set_texture(self.cur_texture_index)

    def enter_building(self, building):
        self.outside = False
        self.stop_completely()
        self.assign_enemy(None)
        self.remove_from_map_quadtree()
        self.game.units_manager.unselect(self)
        building.on_soldier_enter(soldier=self)

    def leave_building(self, building):
        x, y = building.position
        self.position = self.game.pathfinder.get_closest_walkable_position(x, y)
        self.insert_to_map_quadtree()
        self.outside = True

    def restore_health(self):
        wounds = round(self._max_health - self.health, 3)
        health_gained = min(self.health_restoration, wounds)
        self.health += health_gained

    def create_death_animation(self):
        self.spawn_corpse()

    def spawn_corpse(self):
        corpse_name = f'{self.colored_name}_corpse.png'
        self.game.spawn(corpse_name, self.position, self.facing_direction)


class Engineer(Soldier):

    @classmethod
    def create_ui_buttons(cls, x, y):
        pass


class UnitsOrderedDestinations:
    """
    When Player sends hos Units somewhere on the map by mouse-clicking there,
    this class stores all positions each Unit was assigned as it's final
    destination by the Pathfinder. Game uses these positions to display on the
    ordered destinations on the screen for the Player convenience.
    """
    size = 5 / 90

    def __init__(self):
        self.destinations = []
        self.time_left = 0

    def new_destinations(self, destinations: List[Point]):
        self.destinations = destinations
        self.time_left = 90

    def on_update(self, delta_time):
        if self.time_left > 0:
            self.time_left -= 1
        else:
            self.destinations.clear()

    def draw(self):
        for (x, y) in self.destinations:
            draw_circle_filled(x, y, self.size * self.time_left, GREEN, 6)
