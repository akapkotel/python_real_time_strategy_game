#!/usr/bin/env python
from __future__ import annotations

import random

from abc import abstractmethod
from collections import defaultdict
from functools import cached_property
from typing import Dict, List, Optional, Set, Tuple, Union, Any

from arcade import rand_in_circle
from arcade.arcade_types import Color, Point

from game import Game, BASIC_UI
from gameobjects.gameobject import GameObject
from map.map import MapNode, Sector, TILE_WIDTH, position_to_map_grid
from missions.research import Technology
from utils.classes import Observed, Observer
from utils.colors import GREEN, RED
from utils.data_types import FactionId, TechnologyId, GridPosition
from utils.logging import log
from utils.functions import (
    ignore_in_editor_mode, new_id, add_player_color_to_name
)
from utils.geometry import (
    is_visible, clamp, find_area, precalculate_circular_area_matrix
)
from utils.scheduling import EventsCreator


# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!
from utils.timing import timer

FUEL = 'fuel'
FOOD = 'food'
ENERGY = 'energy'
STEEL = 'steel'
ELECTRONICS = 'electronics'
CONSCRIPTS = 'conscripts'


class Faction(EventsCreator, Observer, Observed):
    """
    Faction bundles several Players into one team of allies and helps tracking
    who is fighting against whom.
    """
    game: Optional[Game] = None

    def __init__(self,
                 id: Optional[FactionId] = None,
                 name: Optional[str] = None,
                 friends: Optional[Set[FactionId]] = None,
                 enemies: Optional[Set[FactionId]] = None):
        EventsCreator.__init__(self)
        Observer.__init__(self)
        Observed.__init__(self)
        self.id = id or new_id(self.game.factions)
        self.name: str = name or f'Faction {self.id}'

        self.friendly_factions: Set[FactionId] = friends or set()
        self.enemy_factions: Set[FactionId] = enemies or set()

        self.players = set()
        self.leader: Optional[Player] = None

        self.units: Set[Unit] = set()
        self.buildings: Set[Building] = set()
        self.known_enemies: Set[PlayerEntity] = set()

        self.attach(observer=self.game)

    def __repr__(self) -> str:
        return self.name

    def on_being_attached(self, attached: Observed):
        attached: Player
        self.players.add(attached)
        if self.leader is None:
            self.new_leader(attached)

    def notify(self, attribute: str, value: Any):
        pass

    def on_being_detached(self, detached: Observed):
        detached: Player
        self.players.discard(detached)
        if detached is self.leader and self.players:
            self.new_leader()

    def new_leader(self, leader: Optional[Player] = None):
        self.leader = leader or sorted(self.players, key=lambda x: x.id)[-1]

    def is_enemy(self, other: Faction) -> bool:
        return other.id in self.enemy_factions

    def start_war_with(self, other: Faction):
        self.friendly_factions.discard(other.id)
        self.enemy_factions.add(other.id)
        other.friendly_factions.discard(self.id)
        other.enemy_factions.add(self.id)

    def cease_fire(self, other: Faction):
        self.enemy_factions.discard(other.id)
        other.enemy_factions.discard(self.id)

    def start_alliance(self, other: Faction):
        self.cease_fire(other)
        self.friendly_factions.add(other.id)
        other.cease_fire(self)
        other.friendly_factions.add(self.id)

    def update(self):
        log(f'Updating faction: {self.name} players: {self.players}')
        self.known_enemies.clear()
        for player in self.players:
            player.update()

    def __getstate__(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'friends': self.friendly_factions,
            'enemies': self.enemy_factions
        }

    def save(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'friends': self.friendly_factions,
            'enemies': self.enemy_factions
        }


class ResourcesManager:
    game: Optional[Game] = None
    resources_names = FUEL, FOOD, ENERGY, STEEL, ELECTRONICS, CONSCRIPTS

    def __init__(self):
        for resource_name in self.resources_names:
            setattr(self, resource_name, 1000)
            setattr(self, f"{resource_name}_yield_per_frame", 0.0)
            setattr(self, f"{resource_name}_production_efficiency", 1.0)

    def enough_resources_for(self, expense: str) -> bool:
        category = self._identify_expense_category(expense)
        for resource in (STEEL, ELECTRONICS, CONSCRIPTS):
            required_amount = self.game.configs[category][expense][resource]
            if not self.has_resource(resource, required_amount):
                self.notify_player_of_resource_deficit(resource)
                return False
        return True

    def _identify_expense_category(self, expense: str) -> str:
        for category, items in self.game.configs.items():
            if expense in items:
                return category
        raise KeyError(f'No such name ({expense}) in configs files!')

    def resource(self, resource: str) -> int:
        return getattr(self, resource, 0)

    def has_resource(self, resource: str, amount: int = 1) -> bool:
        return self.resource(resource) >= amount

    def notify_player_of_resource_deficit(self, resource: str):
        sound = f'not_enough_{resource}.wav'
        self.game.window.sound_player.play_sound(sound)

    def change_resource_yield_per_frame(self, resource: str, change: float):
        old_yield = getattr(self, f"{resource}_yield_per_frame")
        setattr(self, f"{resource}_yield_per_frame", old_yield + change)

    def _update_resources_stock(self):
        for resource_name in self.resources_names:
            stock = getattr(self, resource_name)
            change = getattr(self, f"{resource_name}_yield_per_frame")
            setattr(self, resource_name, stock + change)

    def consume_resource(self, resource_name: str, amount: float):
        setattr(self, resource_name, getattr(self, resource_name) - abs(amount))

    def add_resource(self, resource_name: str, amount: float):
        setattr(self, resource_name, getattr(self, resource_name) + abs(amount))


class Player(ResourcesManager, EventsCreator, Observer, Observed):

    game: Optional[Game] = None
    cpu = False

    def __init__(self,
                 id: Optional[int] = None,
                 name: Optional[str] = None,
                 color: Optional[Color] = None,
                 faction: Optional[Faction] = None):
        ResourcesManager.__init__(self)
        EventsCreator.__init__(self)
        Observer.__init__(self)
        Observed.__init__(self)
        self.id = id or new_id(self.game.players)
        self.faction: Faction = faction or Faction()
        self.name = name or f'Player {self.id} of faction: {self.faction}'
        self.color = color

        self.known_technologies: Set[int] = set()
        self.current_research: Dict[int, float] = defaultdict()

        self.units: Set[Unit] = set()
        self.buildings: Set[Building] = set()

        self.known_enemies: Set[PlayerEntity] = set()

        self.attach_observers(observers=[self.game, self.faction])

    def __repr__(self) -> str:
        return self.name

    @cached_property
    def is_local_human_player(self) -> bool:
        return self is self.game.local_human_player

    def on_being_attached(self, attached: Observed):
        attached: Union[Unit, Building]
        if isinstance(attached, Unit):
            self._add_unit(attached)
        else:
            self._add_building(attached)

    def _add_unit(self, unit: Unit):
        self.units.add(unit)
        self.faction.units.add(unit)

    def _add_building(self, building: Building):
        self.buildings.add(building)
        self.faction.buildings.add(building)
        self.consume_resource(ENERGY, building.configs['energy_consumption'])

    def notify(self, attribute: str, value: Any):
        pass

    def on_being_detached(self, detached: Observed):
        detached: Union[Unit, Building]
        try:
            self._remove_unit(detached)
        except KeyError:
            self._remove_building(detached)

    def _remove_unit(self, unit: Unit):
        self.units.remove(unit)
        self.faction.units.remove(unit)

    def _remove_building(self, building: Building):
        self.buildings.discard(building)
        self.faction.buildings.discard(building)
        self.add_resource(ENERGY, building.energy_consumption)

    def is_enemy(self, other: Player) -> bool:
        return self.faction.is_enemy(other.faction)

    def start_war_with(self, other: Player):
        if self.faction.leader is self:
            self.faction.start_war_with(other.faction)

    def update(self):
        self.known_enemies.clear()
        self._update_resources_stock()
        # print(self.buildings)

    def update_known_enemies(self, enemies: Set[PlayerEntity]):
        self.known_enemies.update(enemies)
        self.faction.known_enemies.update(enemies)

    @property
    def defeated(self) -> bool:
        return not self.units and not self.buildings

    def knows_all_required(self, required: Tuple[TechnologyId]):
        return all(technology_id in self.known_technologies for technology_id in required)

    def update_known_technologies(self, new_technology: Technology):
        self.known_technologies.add(new_technology.id)
        new_technology.gain_technology_effects(researcher=self)

    def kill(self):
        self.detach_observers()

    def __getstate__(self) -> Dict:
        saved_player = {k: v for (k, v) in self.__dict__.items()}
        saved_player['faction'] = self.faction.id
        saved_player['units'] = set()
        saved_player['buildings'] = set()
        saved_player['known_enemies'] = set()
        saved_player['observed_attributes'] = {}
        return saved_player

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.faction = self.game.factions[self.faction]
        self.observed_attributes = defaultdict(list)
        self.attach_observers(observers=[self.game, self.faction])


class HumanPlayer(Player):
    cpu = False

    def __init__(self,
                 id: Optional[int] = None,
                 name: Optional[str] = None,
                 color: Optional[Color] = None,
                 faction: Optional[Faction] = None):
        super().__init__(id, name, color, faction)

    def update(self):
        super().update()
        self.update_ui_resource_panel()

    def update_ui_resource_panel(self):
        bundle = self.game.get_bundle(BASIC_UI)
        for resource in self.resources_names:
            label = bundle.find_by_name(name=resource)
            value = int(self.resource(resource))
            label.text = str(value)
            label.text_color = RED if not value else GREEN


class CpuPlayer(Player):
    cpu = True

    def __init__(self,
                 id: Optional[int] = None,
                 name: Optional[str] = None,
                 color: Optional[Color] = None,
                 faction: Optional[Faction] = None):
        super().__init__(id, name, color, faction)


class PlayerEntity(GameObject):
    """
    This is an abstract class for all objects which can be controlled by the
    Player. It contains methods and attributes common for the Unit and Building
    classes, which inherit from PlayerEntity.
    Many attributes are initialized with null values (0, 0.0, etc.) because
    they are set just after spawn with data queried from self.game.config
    dict generated from CSV config file -> see ObjectsFactory class and it's
    'spawn' method.
    """

    def __init__(self,
                 texture_name: str,
                 player: Player,
                 position: Point,
                 robustness: int = 0,
                 id: Optional[int] = None):
        self.colored_name = add_player_color_to_name(texture_name, player.color)
        super().__init__(self.colored_name, robustness, position, id)
        self.map = self.game.map
        self.player: Player = player
        self.faction: Faction = self.player.faction

        # Each Unit or Building keeps a set containing enemies it actually
        # sees and updates this set each frame:
        self.known_enemies: Set[PlayerEntity] = set()

        # this enemy must be assigned by the Player (e.g. by mouse-click)
        self._player_assigned_enemy: Optional[PlayerEntity] = None

        # this enemy is currently targeted, can be obtained automatically:
        self._targeted_enemy: Optional[PlayerEntity] = None

        self.selection_marker: Optional[SelectedEntityMarker] = None

        # this is checked so frequent that it is worth caching it:
        self.is_building = isinstance(self, Building)
        self.is_unit = not self.is_building
        self.is_infantry = isinstance(self, Soldier)

        self._max_health = self.configs['max_health']
        self._health = self._max_health
        self.armour = 0
        self.cover = 0

        # visibility matrix is a list of tuples containing (x, y) indices to be
        # later used in updating current visibility area by adding to the
        # matrix current position
        value = self.configs['visibility_radius']
        self.visibility_matrix = precalculate_circular_area_matrix(value)

        # area inside which all map-nodes are visible for this entity:
        self.observed_grids: Set[GridPosition] = set()
        self.observed_nodes: Set[MapNode] = set()

        # like the visibility matrix, but range should be smaller:
        value = self.configs['attack_radius']
        self.attack_range_matrix = precalculate_circular_area_matrix(value)

        # area inside which every enemy unit could by attacked:
        self.fire_covered: Set[MapNode] = set()

        self._weapons: List[Weapon] = []
        # use this number to animate shot blast from weapon:
        self.barrel_end = self.cur_texture_index
        self._ammunition = 100

        self.experience = 0
        self.kill_experience = 0

        self.attach_observers(observers=[self.game, self.player])

    def __bool__(self) -> bool:
        return self.alive

    @property
    def configs(self):
        category = 'units' if self.is_unit else 'buildings'
        return self.game.configs[category][self.object_name]

    @property
    def alive(self) -> bool:
        return self._health > 0

    @abstractmethod
    def moving(self) -> bool:
        raise NotImplementedError

    @property
    def should_reveal_map(self) -> bool:
        # flag used to avoid enemy units revealing map for human player, only
        # player's units and his allies units reveal map for him:
        return self.faction is self.game.local_human_player.faction

    @property
    def max_health(self) -> float:
        return self._max_health

    @property
    def health(self) -> float:
        return self._health

    @property
    def health_percentage(self) -> int:
        return int(self._health / self._max_health * 100)

    @health.setter
    def health(self, value: float):
        self._health = clamp(value, self._max_health, 0)

    @property
    def weapons(self) -> bool:
        return self._weapons and self.ammunition

    @property
    def ammunition(self) -> bool:
        return self._ammunition > 0

    def assign_enemy(self, enemy: PlayerEntity):
        # used when Player orders this Entity to attack the particular enemy
        self._player_assigned_enemy = enemy

    @property
    def targeted_enemy(self) -> Optional[PlayerEntity]:
        return self._targeted_enemy

    @targeted_enemy.setter
    def targeted_enemy(self, enemy: Optional[PlayerEntity]):
        self._targeted_enemy = enemy

    @staticmethod
    @abstractmethod
    def unblock_map_node(node: MapNode):
        raise NotImplementedError

    @abstractmethod
    def block_map_node(self, node: MapNode):
        raise NotImplementedError

    @abstractmethod
    def update_current_sector(self):
        raise NotImplementedError

    def on_update(self, delta_time: float = 1/60):
        if self.should_reveal_map:
            self.game.fog_of_war.reveal_nodes(self.observed_grids)
        self.update_known_enemies_set()
        self.update_battle_behaviour()
        super().on_update(delta_time)

    def draw(self):
        if self.is_rendered:
            super().draw()

    @property
    def should_be_rendered(self) -> bool:
        return self in self.game.local_drawn_units_and_buildings and self.on_screen

    @abstractmethod
    def update_observed_area(self, *args, **kwargs):
        """
        Find which MapNodes are inside visibility radius of this Entity and
        update accordingly visible area on the map and reveal Fog of War.
        Units and Building implement this method in different way.
        """
        raise NotImplementedError

    def calculate_observed_area(self) -> Set[GridPosition]:
        position = position_to_map_grid(*self.position)
        circular_area = find_area(*position, self.visibility_matrix)
        return set(self.map.in_bounds(circular_area))

    def update_known_enemies_set(self):
        if enemies := self.scan_for_visible_enemies():
            self.player.update_known_enemies(enemies)
        self.known_enemies = enemies

    @ignore_in_editor_mode
    def update_battle_behaviour(self):
        if self.weapons and self.known_enemies:
            self._targeted_enemy = self.update_targeted_enemy()
            self.fight_enemies()
        elif self.is_unit:
            self.run_away()

    def update_targeted_enemy(self):
        """
        Set the random or weakest of the enemies in range of this entity
        weapons as the current hit to attack if not targeting any yet.
        """
        in_range = self.in_range
        for enemy in (self._player_assigned_enemy, self._targeted_enemy):
            if enemy is not None and in_range(enemy):
                return enemy
        else:
            if in_range := [e for e in self.known_enemies if in_range(e)]:
                return sorted(in_range, key=lambda e: e.health)[0]

    @abstractmethod
    def fight_enemies(self):
        raise NotImplementedError

    @abstractmethod
    def run_away(self):
        raise NotImplementedError

    def scan_for_visible_enemies(self) -> Set[PlayerEntity]:
        enemies = []
        for sector in self.get_sectors_to_scan_for_enemies():
            for player_id, entities in sector.units_and_buildings.items():
                if self.game.players[player_id].is_enemy(self.player):
                    enemies.extend(entities)
        return {e for e in enemies if self.inside_area(e, self.observed_nodes)}

    def inside_area(self, other: Union[Unit, Building], area) -> bool:
        if other.is_unit:
            return other.current_node in self.observed_nodes
        else:
            return len(self.observed_nodes & other.occupied_nodes) > 0

    def in_range(self, other: Union[Unit, Building]) -> bool:
        if other.is_unit:
            return other.current_node in self.fire_covered
        else:
            return len(self.fire_covered & other.occupied_nodes) > 0

    def engage_enemy(self, enemy: PlayerEntity):
        if enemy.alive:
            self.attack(enemy)
        else:
            self._targeted_enemy = None

    def attack(self, enemy):
        for weapon in (w for w in self._weapons if w.reloaded()):
            weapon.shoot(enemy)
        self.check_if_enemy_destroyed(enemy)

    def check_if_enemy_destroyed(self, enemy: PlayerEntity):
        if not enemy.alive:
            self.experience += enemy.kill_experience
            self.known_enemies.discard(enemy)
            self._targeted_enemy = None

    @abstractmethod
    def get_sectors_to_scan_for_enemies(self) -> List[Sector]:
        raise NotImplementedError

    def visible_for(self, other: PlayerEntity) -> bool:
        obstacles = self.game.buildings
        return is_visible(self.position, other.position, obstacles)

    def is_enemy(self, other: PlayerEntity) -> bool:
        return self.faction.is_enemy(other.faction)

    @property
    def selectable(self) -> bool:
        return self.player.is_local_human_player

    @property
    def is_selected(self) -> bool:
        raise NotImplementedError

    def damaged(self) -> bool:
        return self._health < self._max_health

    def on_being_damaged(self, damage: float):
        """
        :param damage: float
        :return: bool -- if hit entity was destroyed/kiled or not,
        it is propagated to the damage-dealer.
        """
        self.create_hit_audio_visual_effects()
        deviation = self.game.settings.damage_randomness_factor
        self.health -= random.gauss(damage, damage * deviation)
        self.health_check()

    def health_check(self):
        if self._health <= 0:
            self.kill()

    def create_hit_audio_visual_effects(self):
        position = rand_in_circle(self.position, self.collision_radius // 3)
        # self.game.create_effect(Explosion(*position, 'HITBLAST'))

    def kill(self):
        if self.is_selected and self.player is self.game.local_human_player:
            self.game.units_manager.unselect(entity=self)
        super().kill()

    def save(self) -> Dict:
        saved_entity = super().save()
        saved_entity.update(
            {
                'player': self.player.id,
                '_health': self._health,
                'experience': self.experience
            }
        )
        return saved_entity

    def load(self, loaded_data: Dict):
        """
        After initializing Entity during loading saved game state, load all the
        attributes which were saved, but not passed to __init__ method.
        """
        ignored = ('object_name', 'id', 'player', 'position', 'path')
        for key, value in loaded_data.items():
            if key not in ignored:
                setattr(self, key, value)


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from units.weapons import Weapon
    from units.units import Unit, Soldier
    from buildings.buildings import Building
    from units.unit_management import SelectedEntityMarker

