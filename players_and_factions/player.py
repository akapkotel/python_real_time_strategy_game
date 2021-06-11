#!/usr/bin/env python
from __future__ import annotations

import random

from abc import abstractmethod
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union

from arcade import rand_in_circle
from arcade.arcade_types import Color, Point

from game import Game, UPDATE_RATE
from gameobjects.gameobject import GameObject, Robustness
from map.map import MapNode, Sector, TILE_WIDTH
from missions.research import Technology
from utils.data_types import FactionId, TechnologyId
from utils.logging import log
from utils.functions import ignore_in_editor_mode
from utils.geometry import distance_2d, is_visible, calculate_circular_area
from utils.ownership_relations import ObjectsOwner, OwnedObject
from utils.scheduling import EventsCreator


# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!

FUEL = 'fuel'
FOOD = 'food'
ENERGY = 'energy'
STEEL = 'steel'
ELECTRONICS = 'electronics'
CONSCRIPTS = 'conscripts'


def new_id(objects: Dict) -> int:
    if objects:
        return max(objects.keys()) << 1
    else:
        return 2


class Faction(EventsCreator, ObjectsOwner, OwnedObject):
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
        ObjectsOwner.__init__(self)
        OwnedObject.__init__(self)
        self.id = id or new_id(self.game.factions)
        self.name: str = name or f'Faction {self.id}'

        self.friendly_factions: Set[FactionId] = friends or set()
        self.enemy_factions: Set[FactionId] = enemies or set()

        self.players = set()
        self.leader: Optional[Player] = None

        self.units: Set[Unit] = set()
        self.buildings: Set[Building] = set()
        self.known_enemies: Set[PlayerEntity] = set()

        self.register_to_objectsowners(self.game)

    def __repr__(self) -> str:
        return self.name

    def register(self, acquired: OwnedObject):
        acquired: Player
        self.players.add(acquired)
        if self.leader is None:
            self.new_leader(acquired)

    def unregister(self, owned: OwnedObject):
        owned: Player
        self.players.discard(owned)
        if owned is self.leader:
            self.new_leader()

    def new_leader(self, leader: Optional[Player] = None):
        self.leader = leader or sorted(self.players, key=lambda x: x.id)[-1]

    def get_notified(self, *args, **kwargs):
        pass

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
        log(f'Updating faction: {self.name}')
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
    resources_names = FUEL, FOOD, ENERGY, STEEL, ELECTRONICS, CONSCRIPTS

    def __init__(self):
        for resource_name in self.resources_names:
            setattr(self, resource_name, 0)
            setattr(self, f"{resource_name}_yield_per_frame", 0.0)
            setattr(self, f"{resource_name}_production_efficiency", 1.0)

    def has_resource(self, resource: str, amount: int = 1):
        return getattr(self, resource, 0) >= amount

    def change_resource_yield_per_frame(self, resource: str, change: float):
        old_yield = getattr(self, f"{resource}_yield_per_frame")
        setattr(self, f"{resource}_yield_per_frame", old_yield + change)

    def _update_resources_stock(self):
        for resource_name in self.resources_names:
            stock = getattr(self, resource_name)
            change = getattr(self, f"{resource_name}_yield_per_frame")
            setattr(self, resource_name, stock + change)

    def consume_resource(self, resource_name: str, amount: float):
        stock = getattr(self, resource_name)
        setattr(self, resource_name, stock - amount)


class Player(ResourcesManager, EventsCreator, ObjectsOwner, OwnedObject):
    game: Optional[Game] = None
    cpu = False

    def __init__(self,
                 id: Optional[int] = None,
                 name: Optional[str] = None,
                 color: Optional[Color] = None,
                 faction: Optional[Faction] = None):
        ResourcesManager.__init__(self)
        EventsCreator.__init__(self)
        ObjectsOwner.__init__(self)
        OwnedObject.__init__(self)
        self.id = id or new_id(self.game.players)
        self.faction: Faction = faction or Faction()
        self.name = name or f'Player {self.id} of faction: {self.faction}'
        self.color = color

        self.known_technologies: Set[int] = set()
        self.current_research: Dict[int, float] = defaultdict()

        self.technology_required: Optional[int] = None
        self.resources_required: Optional[Tuple[str]] = None

        self.units: Set[Unit] = set()
        self.buildings: Set[Building] = set()

        self.known_enemies: Set[PlayerEntity] = set()
        
        self.register_to_objectsowners(self.game, self.faction)

    def __repr__(self) -> str:
        return self.name

    def register(self, acquired: OwnedObject):
        acquired: Union[Unit, Building]
        if isinstance(acquired, Unit):
            self.units.add(acquired)
            self.faction.units.add(acquired)
        else:
            self.buildings.add(acquired)
            self.faction.buildings.add(acquired)

    def unregister(self, owned: OwnedObject):
        owned: Union[Unit, Building]
        try:
            self.units.remove(owned)
            self.faction.units.remove(owned)
        except KeyError:
            self.buildings.discard(owned)
            self.faction.buildings.discard(owned)

    def get_notified(self, *args, **kwargs):
        pass

    def is_enemy(self, other: Player) -> bool:
        return self.faction.is_enemy(other.faction)

    def start_war_with(self, other: Player):
        if self.faction.leader is self:
            self.faction.start_war_with(other.faction)

    def update(self):
        self.known_enemies.clear()
        self.clear_mutually_detected_enemies()
        self._update_resources_stock()

    def update_known_enemies(self, enemies: Set[PlayerEntity]):
        self.known_enemies.update(enemies)
        self.faction.known_enemies.update(enemies)

    def clear_mutually_detected_enemies(self):
        for entity in self.units.union(self.buildings):
            entity.mutually_detected_enemies.clear()

    @property
    def defeated(self) -> bool:
        return not self.units and not self.buildings

    def knows_all_required(self, required: Tuple[TechnologyId]):
        return all(technology_id in self.known_technologies for technology_id in required)

    def update_known_technologies(self, new_technology: Technology):
        self.known_technologies.add(new_technology.id)
        new_technology.gain_technology_effects(researcher=self)

    def kill(self):
        self.unregister_from_all_owners()

    def __getstate__(self) -> Dict:
        saved_player = self.__dict__.copy()
        saved_player['faction'] = self.faction.id
        saved_player['units'] = set()
        saved_player['buildings'] = set()
        saved_player['known_enemies'] = set()
        return saved_player

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.faction = self.game.factions[self.faction]


class CpuPlayer(Player):
    cpu = True

    def __init__(self,
                 id: Optional[int] = None,
                 name: Optional[str] = None,
                 color: Optional[Color] = None,
                 faction: Optional[Faction] = None):
        super().__init__(id, name, color, faction)

    def update(self):
        super().update()


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
    # game: Optional[Game] = None

    production_per_frame = UPDATE_RATE / 10  # 10 seconds to build
    production_cost = {'steel': 0, 'conscripts': 0, 'energy': 0}

    def __init__(self,
                 entity_name: str,
                 player: Player,
                 position: Point,
                 robustness: Robustness = 0,
                 id: Optional[int] = None):
        GameObject.__init__(self, entity_name, robustness, position, id)
        self.map = self.game.map

        self.player: Player = player
        self.faction: Faction = self.player.faction

        # Each Unit or Building keeps a set containing enemies it actually
        # sees and updates this set each frame:
        self.known_enemies: Set[PlayerEntity] = set()

        # when an Unit or Building detect enemy, enemy detects it too
        # automatically, to decrease number of is_visible functions calls:
        self.mutually_detected_enemies: Set[PlayerEntity] = set()

        self.nearby_friends: Set[PlayerEntity] = set()

        self.targeted_enemy: Optional[PlayerEntity] = None

        self.selection_marker: Optional[SelectedEntityMarker] = None

        # this is checked so frequent that it is worth caching it:
        self.is_building = isinstance(self, Building)
        self.is_unit = not self.is_building
        self.is_infantry = isinstance(self, Infantry)

        self._max_health = 100
        self._health = self._max_health
        self.armour = 0
        self.cover = 0

        self.detection_radius = TILE_WIDTH * 8  # how far this Entity can see
        self.attack_radius = TILE_WIDTH * 5
        self.observed_nodes: Set[MapNode] = set()

        self._weapons: List[Weapon] = []
        # use this number to animate shot blast from weapon:
        self.barrel_end = self.cur_texture_index
        self._ammunition = 100

        self.experience = 0

        self.register_to_objectsowners(self.game, self.player)

    @abstractmethod
    def moving(self) -> bool:
        raise NotImplementedError

    @property
    def health(self) -> float:
        return self._health

    @property
    def weapons(self) -> bool:
        return self._weapons and self.ammunition

    @property
    def ammunition(self) -> bool:
        return self._ammunition > 0

    @health.setter
    def health(self, value: float):
        self._health = value

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
        self.update_visibility()
        self.update_nearby_friends()
        self.update_known_enemies_set()
        self.update_targeted_enemy()
        self.update_fighting()
        super().on_update(delta_time)

    @ignore_in_editor_mode
    def update_targeted_enemy(self):
        """
        Set the random or weakest of the enemies in range of this entity
        weapons as the current hit to attack if not targeting any yet.
        """
        if (enemies := self.known_enemies) and self.no_current_target:
            if in_range := [e for e in enemies if e.in_range(self)]:
                if self.experience > 35:
                    self.targeted_enemy = sorted(in_range, key=lambda e: e.health)[0]
                else:
                    self.targeted_enemy = random.choice(in_range)
            else:
                self.targeted_enemy = None

    @ignore_in_editor_mode
    def update_fighting(self):
        if (enemy := self.targeted_enemy) is not None:
            self.fight_or_run_away(enemy)
        elif (enemies := self.known_enemies) and not self.is_building:
            self.move_towards_enemies_nearby(enemies)

    def draw(self):
        if self.is_rendered:
            super().draw()

    @property
    def alive(self) -> bool:
        return self._health > 0

    def update_visibility(self):
        if self in self.game.local_drawn_units_and_buildings:
            if not self.is_rendered:
                self.start_drawing()
        elif self.is_rendered:
            self.stop_drawing()

    @abstractmethod
    def update_observed_area(self, *args, **kwargs):
        """
        Find which MapNodes are inside visibility radius of this Entity and
        update accordingly visible area on the map and reveal Fog of War.
        Units and Building implement this method in different way.
        """
        raise NotImplementedError

    def calculate_observed_area(self) -> Set[MapNode]:
        position = self.map.position_to_grid(*self.position)
        observed_area = calculate_circular_area(*position, 8)
        observed_area = self.map.in_bounds(observed_area)
        return {self.map.nodes[id] for id in observed_area}

    def update_nearby_friends(self):
        self.nearby_friends = self.get_nearby_friends()

    def update_known_enemies_set(self):
        if enemies := self.scan_for_visible_enemies():
            self.player.update_known_enemies(enemies)
            self.notify_detected_enemies_about_self(enemies)
            self.notify_all_nearby_friends_about_enemies(enemies)
        self.known_enemies = enemies.union(self.mutually_detected_enemies)

    def notify_all_nearby_friends_about_enemies(self, enemies):
        """
        By informing other, friendly Units and Buildings about detected
        enemies, we can cut down the number of detection-tests, and more
        congested the area is, the more processing time we save.
        """
        for friend in self.nearby_friends:
            friend.known_enemies.update(enemies)

    def notify_detected_enemies_about_self(self, enemies):
        """
        Informing visible enemy that we are visible for him is an obvious way
        to cut detection-tests by half.
        """
        for enemy in enemies:
            enemy.mutually_detected_enemies.add(self)

    def scan_for_visible_enemies(self) -> Set[PlayerEntity]:
        sectors = self.get_sectors_to_scan_for_enemies()
        enemies = set()
        for sector in sectors:
            for player_id, entities in sector.units_and_buildings.items():
                if self.game.players[player_id].is_enemy(self.player):
                    enemies.update(entities)
        return {e for e in enemies if e.in_observed_area(self)}

    @abstractmethod
    def in_observed_area(self, other) -> bool:
        raise NotImplementedError

    def in_range(self, other: PlayerEntity) -> bool:
        return distance_2d(self.position, other.position) < self.attack_radius

    @property
    def no_current_target(self) -> bool:
        return self.targeted_enemy is None or not self.targeted_enemy.in_range(self)

    def fight_or_run_away(self, enemy: PlayerEntity):
        self.engage_enemy(enemy) if self.weapons else self.run_away(enemy)

    def engage_enemy(self, enemy: PlayerEntity):
        if enemy.alive:
            for weapon in self._weapons:
                if weapon.effective_against(enemy) and weapon.reload():
                    if was_enemy_killed := weapon.shoot(enemy):
                        self.gain_experience(enemy)
                        self.targeted_enemy = None
        else:
            self.targeted_enemy = None

    def run_away(self, enemy: PlayerEntity):
        raise NotImplementedError

    def gain_experience(self, enemy: PlayerEntity):
        self.experience += 1  # TODO: get experience from configs

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
        return self.player is self.game.local_human_player

    def damaged(self) -> bool:
        return self._health < self._max_health

    @abstractmethod
    def get_nearby_friends(self) -> Set[PlayerEntity]:
        raise NotImplementedError

    def on_being_hit(self, damage: float) -> bool:
        """
        :param damage: float
        :return: bool -- if hit entity was destroyed/kiled or not,
        it is propagated to the damage-dealer.
        """
        self.create_hit_audio_visual_effects()
        self._health -= damage
        return self._health <= 0

    def create_hit_audio_visual_effects(self):
        position = rand_in_circle(self.position, self.collision_radius // 3)
        # self.game.create_effect(Explosion(*position, 'HITBLAST'))

    def kill(self):
        if self.selection_marker is not None:
            self.selection_marker.kill()
        super().kill()

    @abstractmethod
    def move_towards_enemies_nearby(self, known_enemies: Set[PlayerEntity]):
        raise NotImplementedError

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


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from units.weapons import Weapon
    from units.units import Unit, Infantry
    from buildings.buildings import Building
    from units.unit_management import SelectedEntityMarker

