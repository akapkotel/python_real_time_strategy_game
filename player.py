#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Set, Dict, List, Union, Optional
from arcade.arcade_types import Color, Point

from observers import ObjectsOwner, OwnedObject
from gameobject import GameObject, Robustness
from scheduling import EventsCreator
from utils.functions import log, is_visible
from data_types import FactionId
from game import Game, UPDATE_RATE
from map import TILE_WIDTH, MapNode


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
                 name: Optional[str] = None):
        EventsCreator.__init__(self)
        ObjectsOwner.__init__(self)
        OwnedObject.__init__(self)
        self.id = id or new_id(self.game.factions)
        self.name: str = name or f'Faction {self.id}'

        self.friendly_factions: Set[FactionId] = set()
        self.enemy_factions: Set[FactionId] = set()

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


class Player(EventsCreator, ObjectsOwner, OwnedObject):
    game: Optional[Game] = None

    def __init__(self, id=None, name=None, color=None, faction=None, cpu=True):
        EventsCreator.__init__(self)
        ObjectsOwner.__init__(self)
        OwnedObject.__init__(self)
        self.id = id or new_id(self.game.players)
        self.faction: Faction = faction or Faction()
        self.name = name or f'Player {self.id} of faction: {self.faction}'
        self.cpu = cpu
        self.color = color or self.game.next_free_player_color()

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
        log(f'Updating player: {self}')
        self.update_known_enemies()

    def update_known_enemies(self):
        self.known_enemies.clear()
        for unit in self.units:
            self.known_enemies.update(unit.known_enemies)
        self.faction.known_enemies.update(self.known_enemies)


class CpuPlayer(Player):
    # TODO: all Cpu-controlled Player logic!
    pass


class PlayerEntity(GameObject, EventsCreator):
    """
    This is an abstract class for all objects which can be controlled by the
    Player. It contains methods and attributes common for the Unit and Building
    classes, which inherit from PlayerEntity.
    """
    game: Optional[Game] = None

    def __init__(self,
                 entity_name: str,
                 player: Player,
                 position: Point,
                 robustness: Robustness = 0):
        GameObject.__init__(self, entity_name, robustness, position)
        EventsCreator.__init__(self)
        OwnedObject.__init__(self, owners=True)

        self.player: Player = player
        self.faction: Faction = self.player.faction
        self.known_enemies: Set[PlayerEntity] = set()

        self.selection_marker: Optional[SelectedEntityMarker] = None

        self.is_building = isinstance(self, Building)

        self._max_health = 100
        self._health = self._max_health

        self.detection_radius = TILE_WIDTH * 8  # how far this Entity can see

        self.production_per_frame = UPDATE_RATE / 10  # 10 seconds to build

        self.register_to_objectsowners(self.game, self.player, self.game.fog_of_war)

    @property
    def health(self) -> float:
        return self._health

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

    def update(self):
        super().update()
        if self.alive:
            self.update_visibility()
            self.update_known_enemies_set()
        else:
            self.kill()

    @property
    def alive(self) -> bool:
        return self._health > 0

    def update_visibility(self):
        if self in self.game.local_drawn_units_and_buildings:
            if not self.rendered:
                self.start_drawing()
        elif self.rendered:
            self.stop_drawing()

    @property
    def rendered(self) -> bool:
        return self in self.divided_spritelist.drawn

    def update_known_enemies_set(self):
        self.known_enemies = self.scan_for_visible_enemies()

    def scan_for_visible_enemies(self) -> Set[Union[Unit, Building]]:
        potentially_visible = []
        for faction in self.game.factions.values():
            if faction.is_enemy(self.faction):
                potentially_visible.extend(faction.units)
                potentially_visible.extend(faction.buildings)

        visible_enemies: Set[Union[Unit, Building]] = {
            enemy for enemy in potentially_visible if
            enemy.visible_for(self)
        }
        return visible_enemies

    def visible_for(self, other: PlayerEntity) -> bool:
        obstacles = self.game.buildings
        distance = self.detection_radius
        return is_visible(self.position, other.position, obstacles,
                          distance)

    def is_enemy(self, other: Unit) -> bool:
        return self.faction.is_enemy(other.faction)

    @property
    def selectable(self) -> bool:
        return self.player is self.game.local_human_player

    @abstractmethod
    def needs_repair(self) -> bool:
        raise NotImplementedError

    def kill(self):
        if self.selection_marker is not None:
            self.selection_marker.kill()
        super().kill()


if __name__:
    from units import Unit
    from buildings import Building
    from mouse_handling import SelectedEntityMarker
