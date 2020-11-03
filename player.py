#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Set, Dict, List, Union, Optional
from arcade.arcade_types import Color, Point

from observers import ObjectsOwner, OwnedObject
from gameobject import GameObject, Robustness
from scheduling import EventsCreator
from utils.functions import log
from data_types import FactionId, PlayerId
from game import Game, UPDATE_RATE


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
        self.register_to_objectsowners(self.game)

    def __repr__(self) -> str:
        return self.name

    def register(self, acquired: OwnedObject):
        acquired: Player
        self.players.add(acquired)

    def unregister(self, owned: OwnedObject):
        owned: Player
        self.players.discard(owned)

    def get_notified(self, *args, **kwargs):
        pass

    def is_enemy(self, other: Faction) -> bool:
        return other.id in self.enemy_factions

    def start_war(self, other: Faction):
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

    def units(self) -> List[Unit]:
        faction_units = []
        for player in self.players:
            faction_units.extend(player.units)
        return faction_units

    def buildings(self) -> List[Building]:
        faction_buildings = []
        for player in self.players:
            faction_buildings.extend(player.buildings)
        return faction_buildings

    def update(self):
        log(f'Updating faction: {self.name}')
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
        else:
            self.buildings.add(acquired)

    def unregister(self, owned: OwnedObject):
        owned: Union[Unit, Building]
        try:
            self.units.remove(owned)
        except KeyError:
            self.buildings.discard(owned)

    def get_notified(self, *args, **kwargs):
        pass

    def is_enemy(self, other: Player) -> bool:
        return self.faction.is_enemy(other.faction)

    def update(self):
        log(f'Updating player: {self}')
        self.update_known_enemies()

    def update_known_enemies(self):
        self.known_enemies.clear()
        for unit in self.units:
            self.known_enemies.update(unit.known_enemies)


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
        OwnedObject.__init__(self)

        self.player: Player = player
        self.faction: Faction = self.player.faction
        self.known_enemies: Set[PlayerEntity] = set()

        self.visibility_radius = 0

        self.production_per_frame = UPDATE_RATE / 10  # 10 seconds to build

        self.register_to_objectsowners(self.game, self.player, self.game.fog_of_war)

    def update(self):
        super().update()
        self.update_known_enemies_set()

    def update_known_enemies_set(self):
        self.known_enemies = self.scan_for_visible_enemies()

    def scan_for_visible_enemies(self) -> Set[Union[Unit, Building]]:
        potentially_visible = []
        for faction in self.game.factions.values():
            if faction.is_enemy(self.faction):
                potentially_visible.extend(faction.units())
                potentially_visible.extend(faction.buildings())

        visible_enemies: Set[Union[Unit, Building]] = {
            unit for unit in potentially_visible if unit.visible_for(self)
        }

        return visible_enemies

    def visible_for(self, other: PlayerEntity) -> bool:
        return True

    def is_enemy(self, other: Unit) -> bool:
        return self.faction.is_enemy(other.faction)

    @abstractmethod
    def selectable(self) -> bool:
        raise NotImplementedError


if __name__:
    from units import Unit
    from buildings import Building
