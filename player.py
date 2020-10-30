#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Sequence, Set, Union, Optional
from arcade.arcade_types import Color, Point

from scheduling import EventsCreator, ScheduledEvent, log
from observers import ObjectsOwner, OwnedObject
from gameobject import GameObject, Robustness
from game import Game


class Faction(EventsCreator, ObjectsOwner, OwnedObject):
    """
    Faction bundles several Players into one team of allies and helps tracking
    who is fighting against whom.
    """
    game: Optional[Game] = None

    def __init__(self, id: Optional[int] = None):
        EventsCreator.__init__(self)
        ObjectsOwner.__init__(self)
        OwnedObject.__init__(self)
        self.id = id or len(self.game.players)
        self.friendly_factions: Set[Faction] = set()
        self.players = set()

    def register(self, acquired: OwnedObject):
        acquired: Player
        self.players.add(acquired)

    def unregister(self, owned: OwnedObject):
        owned: Player
        self.players.discard(owned)

    def get_notified(self, *args, **kwargs):
        pass


class Player(EventsCreator, ObjectsOwner, OwnedObject):
    game: Optional[Game] = None

    def __init__(self, color: Color, faction: None, cpu: True):
        EventsCreator.__init__(self)
        ObjectsOwner.__init__(self)
        OwnedObject.__init__(self)
        self.id = len(self.game.players)
        self.cpu = cpu
        self.color = color
        self.faction: Faction = faction or Faction()

        self.units: Set[Unit] = set()
        self.buildings: Set[Building] = set()

        self.known_enemies: Set[PlayerEntity] = set()
        
        self.register_to_objectsowners(self.game, self.faction)
        
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

    def is_enemy(self, other: Player):
        return self.faction is not other.faction

    def update_known_enemies(self):
        self.known_enemies.clear()
        for unit in self.units:
            self.known_enemies.update(unit.known_enemies)


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

        self.register_to_objectsowners(self.game, self.player, self.game.fog_of_war)

    def update_known_enemies_set(self):
        # get new set of visible and alive enemies:
        visible_enemies = self.scan_for_visible_enemies()

        # update known set with new visible enemies:
        self.register_new_enemies(visible_enemies)

        # remove enemies which are no longer visible from known set:
        self.unregister_lost_enemies(visible_enemies)

        self.known_enemies = visible_enemies

    def unregister_lost_enemies(self, visible_enemies: Set[PlayerEntity]):
        lost_enemies = self.known_enemies.difference(visible_enemies)
        for enemy in lost_enemies:
            self.player.known_enemies.discard(enemy)

    def register_new_enemies(self, visible_enemies: Set[PlayerEntity]):
        new_enemies = visible_enemies.difference(self.known_enemies)
        for enemy in new_enemies:
            self.player.known_enemies.add(enemy)

    @staticmethod
    def scan_for_visible_enemies() -> Set[Union[Unit, Building]]:
        enemies: Set[Union[Unit, Building]] = set()
        # TODO: determine which enemy Units are visible for this Unit
        return enemies


if __name__:
    from units import Unit
    from buildings import Building
