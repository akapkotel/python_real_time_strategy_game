#!/usr/bin/env python
from __future__ import annotations

import random

from abc import abstractmethod
from collections import deque
from typing import Deque, List, Dict, Optional, Set, Union, cast

import PIL
from arcade import (
    SpriteList, Sprite, AnimatedTimeBasedSprite, load_textures,
    draw_circle_filled
)
from arcade.arcade_types import Point

from effects.explosions import Explosion
from buildings.buildings import Building
from map.map import (
    GridPosition, MapNode, MapPath, Pathfinder, Sector, normalize_position,
    position_to_map_grid
)
from players_and_factions.player import Player, PlayerEntity
from utils.enums import UnitWeight
from utils.colors import GREEN
from utils.scheduling import ScheduledEvent
from utils.functions import get_path_to_file
from utils.geometry import (
    precalculate_possible_sprites_angles, calculate_angle, distance_2d,
    vector_2d, ROTATION_STEP, ROTATIONS
)
from .weapons import Weapon


class Unit(PlayerEntity):
    """
    Unit is a PlayerEntity which can move on map.
    """
    angles = precalculate_possible_sprites_angles()

    def __init__(self,
                 unit_name: str,
                 player: Player,
                 weight: UnitWeight,
                 position: Point,
                 id: Optional[int] = None):
        PlayerEntity.__init__(self, unit_name, player, position, id=id)
        # Since we do not rotate actual Sprite, but change it's texture to show
        # the correctly rotated Units on the screen, use 'virtual' rotation to
        # keep track of the Unit rotation angle without rotating actual Sprite:
        self.virtual_angle = 0

        self.weight: UnitWeight = weight
        self.visibility_radius = 100

        # pathfinding and map-related:
        self.position = normalize_position(*self.position)
        self.reserved_node = None
        self.current_node = self.map.position_to_node(*self.position)
        self.block_map_node(self.current_node)
        self.current_sector: Optional[Sector] = None
        self.update_current_sector()

        self.path: Deque[GridPosition] = deque()
        self.path_wait_counter: int = 0
        self.awaited_path: Optional[MapPath] = None

        self.max_speed = 0
        self.current_speed = 0
        self.rotation_speed = 0

        self.permanent_units_group: int = 0
        self.navigating_group = None

        self.explosion_name = 'EXPLOSION'
        # self.update_explosions_pool()

    def update_explosions_pool(self):
        """
        Assure that there would be enough Explosion instances in the pool to
        get one when this Unit is destroyed.
        """
        name = self.explosion_name
        required = len([u for u in self.game.units if u.explosion_name == name])
        self.game.explosions_pool.add(name, required)

    @abstractmethod
    def _load_textures_and_reset_hitbox(self, unit_name: str):
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
        TODO: change it to matrix 8x8 textures - 1 row for each hull angle
         and 1 column for each turret angle.
        """
        index = self.angles[int(angle_to_target)]
        self.set_texture(index)

    @property
    def moving(self) -> float:
        return self.change_x or self.change_y

    def reached_destination(self, destination: Union[MapNode, GridPosition]) -> bool:
        try:
            return destination.grid == self.current_node.grid
        except AttributeError:
            return destination == self.current_node.grid

    def nearby(self, position: Union[MapNode, GridPosition]) -> bool:
        adjacent_grids = {n.grid for n in self.current_node.adjacent_nodes}
        try:
            return position.grid in adjacent_grids
        except AttributeError:
            return position in adjacent_grids

    def heading_to(self, destination: Union[MapNode, GridPosition]):
        return self.path and self.path[0] == self.map.map_grid_to_position(destination)

    def on_update(self, delta_time: float = 1/60):
        if self.alive:
            super().on_update(delta_time)

            new_current_node = self.map.position_to_node(*self.position)
            if self in self.game.local_human_player.faction.units:
                self.update_observed_area(new_current_node)

            self.update_blocked_map_nodes(new_current_node)
            self.update_current_sector()
            self.update_pathfinding()
        else:
            self.kill()

    def update_observed_area(self, new_current_node: MapNode):
        if self.observed_nodes and new_current_node == self.current_node:
            observed = self.observed_nodes
        else:
            self.observed_nodes = observed = self.calculate_observed_area()
        self.game.fog_of_war.reveal_nodes(n.grid for n in observed)

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

    def wait_for_free_path(self, path: Union[deque, MapPath]):
        """
        Waiting for free path is useful when next node is only temporarily
        blocked (blocking Unit is moving) and allows to avoid pathfinding
        the path with A* algorthm. Instead, Unit 'shelves' currently found
        path and after 1 second 'unshelves' it in countdown_waiting method.
        """
        self.path_wait_counter = self.game.timer['s'] + 1
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
            destination = self.map.position_to_map_grid(*self.path[-1])
            self.move_to(destination)

    def find_free_tile_to_unblock_way(self, path) -> bool:
        if adjacent := self.current_node.walkable_adjacent:
            free_tile = random.choice(adjacent)
            self.move_to(free_tile.grid)
            return True
        return False

    def update_current_sector(self):
        if (sector := self.current_node.sector) != self.current_sector:
            if (current_sector := self.current_sector) is not None:
                current_sector.discard_entity(self)
            self.current_sector = sector
            sector.add_player_entity(self)

    def update_pathfinding(self):
        if self.awaited_path is not None:
            self.countdown_waiting()
        if self.path:
            self.follow_path()
        else:
            self.stop()

    def countdown_waiting(self):
        if self.game.timer['s'] == self.path_wait_counter:
            path = self.awaited_path
            node = self.map.position_to_node(*path[0])
            if node.walkable or len(path) < 20:
                self.restart_path(path)
            else:
                self.wait_for_free_path(path)

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
        if (distance_left := distance_2d(self.position, destination)) <= speed:
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
        # self.angle_to_texture(angle)
        self.current_speed = speed = min(distance_left, self.max_speed)
        self.change_x, self.change_y = vector_2d(angle, speed)

    def move_to(self, destination: GridPosition):
        self.cancel_path_requests()
        start = position_to_map_grid(*self.position)
        self.game.pathfinder.request_path(self, start, destination)

    def create_new_path(self, new_path: MapPath):
        old_path = [self.path.popleft()] if self.path else []
        self.path.clear()
        self.path.extend(old_path + new_path[1:])
        self.awaited_path = None
        self.unschedule_earlier_move_orders()

    def unschedule_earlier_move_orders(self):
        for event in (e for e in self.scheduled_events if e.function == self.move_to):
            self.unschedule_event(event)

    def cancel_path_requests(self):
        self.game.pathfinder.cancel_unit_path_requests(self)

    def stop_completely(self):
        self.set_navigating_group(navigating_group=None)
        self.cancel_path_requests()
        self.awaited_path = None
        self.path.clear()
        self.stop()

    def get_sectors_to_scan_for_enemies(self) -> List[Sector]:
        return [self.current_sector] + self.current_sector.adjacent_sectors()

    def in_observed_area(self, other: PlayerEntity) -> bool:
        return self.current_node in other.observed_nodes

    def visible_for(self, other: PlayerEntity) -> bool:
        other: Union[Unit, Building]
        if self.player is self.game.local_human_player and not other.is_unit:
            if other.current_node not in self.observed_nodes:
                return False
        return super().visible_for(other)

    def get_nearby_friends(self) -> Set[PlayerEntity]:
        return self.current_sector.get_entities(self.player.id)

    def set_permanent_units_group(self, index: int = 0):
        if (cur_index := self.permanent_units_group) and cur_index != index:
            try:
                self.game.units_manager.permanent_units_groups[cur_index].discard(self)
            except KeyError:
                pass
        self.permanent_units_group = index

    def target_enemy(self, enemy: Optional[PlayerEntity] = None):
        """Call this method with 'None' to cancel current targeted enemy."""
        self.targeted_enemy = enemy

    def move_towards_enemies_nearby(self, known_enemies: Set[PlayerEntity]):
        """
        When Unit detected enemies but they are out of attack range, it can
        move closer to engage them.
        """
        if not self.has_destination:
            enemy_to_attack = random.choice([e for e in known_enemies])
            position = self.game.pathfinder.get_closest_walkable_position(
                *enemy_to_attack.position)
            self.move_to(position_to_map_grid(*position))

    def kill(self):
        self.current_sector.discard_entity(self)
        self.set_permanent_units_group()
        self.clear_all_blocked_nodes()
        self.create_death_animation()
        self.stop_completely()
        super().kill()

    def set_navigating_group(self, navigating_group):
        if self.navigating_group is not None:
            self.navigating_group.discard(self)
        self.navigating_group = navigating_group

    def clear_all_blocked_nodes(self):
        for node in (self.current_node, self.reserved_node):
            self.unblock_map_node(node) if node is not None else ...

    def create_death_animation(self):
        self.game.create_effect(Explosion, 'EXPLOSION', *self.position)
        self.game.window.sound_player.play_sound('explosion.wav')

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


class Vehicle(Unit):
    """An interface for all Units which are engine-powered vehicles."""

    def __init__(self, unit_name: str, player: Player, weight: UnitWeight,
                 position: Point, id: int = None):
        super().__init__(unit_name, player, weight, position, id)
        thread_texture = f'{self.object_name.rsplit("_", 1)[0]}_threads.png'
        self.thread_texture = get_path_to_file(thread_texture)
        self.threads_time = 0

        self.fuel = 100.0
        self.fuel_consumption = 0.0

    def _load_textures_and_reset_hitbox(self, unit_name: str):
        name = get_path_to_file(unit_name)
        image = PIL.Image.open(name)
        width, height = image.size[0] // 8, image.size[1]
        self.textures = load_textures(
            get_path_to_file(unit_name),
            [(i * width, 0, width, height) for i in range(8)]
        )

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        if self.moving:
            self.consume_fuel()
            if self.game.settings.vehicles_threads:
                self.leave_threads()

    def consume_fuel(self):
        self.fuel -= self.fuel_consumption

    def leave_threads(self):
        if self.is_rendered:
            if self.threads_time > 4:
                self.threads_time = 0
                self.game.vehicles_threads.append(
                    VehicleThreads(self.thread_texture,
                                   self.cur_texture_index,
                                   *self.position),
                )
            else:
                self.threads_time += 1

    def kill(self):
        self.spawn_wreck()
        super().kill()

    def spawn_wreck(self):
        wreck_name = f'{self.object_name.rsplit("_", 1)[0]}_wreck.png'
        wreck = self.game.spawner.spawn(
            wreck_name, None, self.position, self.cur_texture_index
        )
        self.configure_wreck(wreck)

    def configure_wreck(self, wreck):
        wreck.register_to_objectsowners(self.game)
        wreck.schedule_event(ScheduledEvent(wreck, 10.0, wreck.kill))
        map_tile = self.map.position_to_node(*wreck.position)
        map_tile._allowed_for_pathfinding = False


class VehicleThreads(Sprite):

    def __init__(self, texture, index, x, y):
        super().__init__(texture, center_x=x, center_y=y)
        self.textures = load_textures(
            texture, [(i * 29, 0, 29, 28) for i in range(8)]
        )
        self.set_texture(index)

    def on_update(self, delta_time: float = 1 / 60):
        # threads slowly disappearing through time
        if self.alpha > 1:
            self.alpha -= 2
        else:
            self.kill()


class Tank(Vehicle):

    def __init__(self, unit_name: str, player: Player, weight: UnitWeight,
                 position: Point, id: int = None):
        super().__init__(unit_name, player, weight, position, id)
        # combine texture from these two indexes:
        self.hull_texture_index = random.randint(0, ROTATIONS - 1)
        self.turret_texture_index = random.randint(0, ROTATIONS - 1)
        self.fake_angle = ROTATION_STEP * self.hull_texture_index

        self._load_textures_and_reset_hitbox(unit_name)
        self.turret_aim_target = None
        self._weapons.append(Weapon(name='tank_light_gun', owner=self))
        self.barrel_end = self.turret_texture_index

        self.threads_time = 0

    def _load_textures_and_reset_hitbox(self, unit_name: str):
        """
        Create 8 lists of 8-texture spritesheets for each combination of hull
        and turret directions.
        """
        name = get_path_to_file(unit_name)
        image = PIL.Image.open(name)
        width, height = image.size[0] // 8, image.size[1] // 8
        self.textures = [load_textures(get_path_to_file(unit_name),
            [(i * width, j * height, width, height) for i in range(8)]) for j in range(8)
        ]
        self.set_texture(self.hull_texture_index)
        self.set_hit_box(self.texture.hit_box_points)

    def set_rotated_texture(self):
        if (enemy := self.turret_aim_target) is not None:
            self.set_hull_and_turret_texture(enemy)
        else:
            self.angle_to_texture(self.virtual_angle)

    def set_hull_and_turret_texture(self, enemy):
        turret_angle = calculate_angle(*self.position, *enemy.position)
        self.angle_to_texture(self.virtual_angle, turret_angle)

    def angle_to_texture(self,
                         hull_angle: float = None,
                         turret_angle: float = None):
        if hull_angle is not None:
            self.hull_texture_index = self.angles[int(hull_angle)]
        # for Tank we need to set it's turret direction too:
        if turret_angle is None:
            self.turret_texture_index = self.hull_texture_index
        else:
            self.turret_texture_index = self.angles[int(turret_angle)]
        self.barrel_end = self.turret_texture_index
        self.set_texture(self.hull_texture_index)

    def set_texture(self, hull_texture_index: int):
        """
        We override original method to work with 2 texture indexes combined:
        first for the hull (which list of textures to use) and second for
        turret for actual texture to be chosen from the list.
        """
        texture = self.textures[hull_texture_index][self.turret_texture_index]
        if texture == self._texture:
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

    def leave_threads(self):
        self.threads_time += 1
        if self.threads_time > 4:
            self.threads_time = 0
            self.game.vehicles_threads.append(
                VehicleThreads(self.thread_texture,
                               self.hull_texture_index,
                               *self.position),
            )

    def engage_enemy(self, enemy: PlayerEntity):
        self.turret_aim_target = enemy
        self.set_hull_and_turret_texture(enemy)
        super().engage_enemy(enemy)

    def spawn_wreck(self):
        wreck_name = f'{self.object_name.rsplit("_", 1)[0]}_wreck.png'
        wreck = self.game.spawner.spawn(
            wreck_name, None, self.position,
            (self.hull_texture_index, self.turret_texture_index)
        )
        self.configure_wreck(wreck)


class Infantry(Unit):

    def __init__(self, unit_name: str, player: Player, weight: UnitWeight,
                 position: Point):
        super().__init__(unit_name, player, weight, position)

        self.max_soldiers = 4
        self.soldiers: SpriteList[Soldier] = SpriteList()
        self.soldiers.extend([Soldier() for _ in range(self.max_soldiers)])

    def _load_textures_and_reset_hitbox(self, unit_name: str):
        pass

    @property
    def needs_reinforcements(self) -> bool:
        return len(self.soldiers) < self.max_soldiers

    def __len__(self):
        return len(self.soldiers)

    @property
    def damaged(self) -> bool:
        return cast(int, self._health) < 25 * len(self.soldiers)

    def on_update(self, delta_time: float = 1/60):
        super().update()
        self.soldiers.on_update(delta_time)
        self.restore_soldiers_health()

    def restore_soldiers_health(self):
        soldier: Soldier
        for soldier in self.soldiers:
            self._health += soldier.restore_health()

    def on_being_hit(self, damage: float) -> bool:
        hit_soldier = random.choice(self.soldiers)
        hit_soldier.on_being_hit(damage)
        return len(self.soldiers) > 0


class Soldier(AnimatedTimeBasedSprite):
    _max_health = 25
    health = _max_health
    health_restoration = 0.003
    weapon: Weapon = None

    def on_being_hit(self, damage: float) -> bool:
        pass

    def restore_health(self) -> float:
        wounds = round(self._max_health - self.health, 3)
        health_gained = min(self.health_restoration, wounds)
        self.health += health_gained
        return health_gained

    def kill(self):
        pass


class UnitsOrderedDestinations:
    """
    When Player sends hos Units somewhere on the map by mouse-clicking there,
    this class stores all positions each Unit was assigned as it's final
    destination by the Pathfinder. Game uses these positions to display on the
    ordered destinations on the screen for the Player convenience.
    """
    size = 5 / 60

    def __init__(self):
        self.destinations = []
        self.time_left = 0

    def new_destinations(self, destinations: List[Point]):
        self.destinations = destinations
        self.time_left = 60

    def on_update(self, delta_time):
        if self.time_left > 0:
            self.time_left -= 1
        else:
            self.destinations.clear()

    def draw(self):
        for (x, y) in self.destinations:
            draw_circle_filled(x, y, self.size * self.time_left, GREEN, 6)