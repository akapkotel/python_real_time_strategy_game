#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from players_and_factions.player import Player, Faction
from utils.logging import log


class Consequence:
    """Consequence is called when a Condition to which it is bound, is met."""

    def __init__(self):
        self.player = None
        self.mission = None

    @abstractmethod
    def execute(self):
        raise NotImplementedError


class AddVictoryPoints(Consequence):

    def __init__(self, amount: int = 1):
        super().__init__()
        self.amount = amount

    def execute(self):
        self.mission.victory_points[self.player.id] += self.amount
        
        
class Defeat(Consequence):
    """
    Set it as a consequence of a Condition to trigger player defeat.
    """

    def __init__(self, player: Player = None):
        super().__init__()
        self.player = player
    
    def execute(self):
        self.mission.end_mission(winner=self.player)


class Victory(Consequence):
    """
    Set it as a consequence of a Condition to trigger HUMAN-PLAYER victory.
    """

    def execute(self):
        self.mission.end_mission(winner=self.mission.game.local_human_player)


class NewCondition(Consequence):

    def __init__(self, condition: Condition):
        super().__init__()
        self.next_condition = condition

    def execute(self):
        self.mission.add(condition=self.next_condition)


class Condition:
    """
    Condition is a flag-class checked against, to evaluate if any of the
    Players achieved his objectives. You can use them as events also.
    """

    def __init__(self, player: Player):
        self.name = self.__class__.__name__
        self.player = player
        self.mission: Optional[Mission] = None
        self.victory_points = 0
        self._consequences = []

    def __str__(self):
        return f'{self.__class__.__name__} for player: {self.player}'

    def set_vp(self, value: int) -> Condition:
        self.victory_points = value
        self.add_consequence(AddVictoryPoints(value))
        return self

    def consequences(self, *consequences: Consequence) -> Condition:
        for consequence in consequences:
            self.add_consequence(consequence)
        return self

    def bind_mission(self, mission: Mission):
        self.mission = mission
        for consequence in self._consequences:
            consequence.mission = mission

    def add_consequence(self, consequence: Consequence):
        if consequence.player is None:
            consequence.player = self.player
        consequence.mission = self.mission
        self._consequences.append(consequence)

    @abstractmethod
    def is_met(self) -> bool:
        raise NotImplementedError

    def execute_consequences(self):
        for consequence in self._consequences:
            consequence.execute()
            log(f'Condition {self} was met!', console=True)


class TimePassed(Condition):

    def __init__(self, player: Player, required_time: int):
        super().__init__(player)
        self.required_time = required_time

    def is_met(self) -> bool:
        return self.mission.game.timer['m'] >= self.required_time


class MapRevealed(Condition):
    def is_met(self) -> bool:
        return len(self.mission.game.fog_of_war.unexplored) == 0


class NoUnitsLeft(Condition):
    """Beware that this Condition checks bot against Units and Buildings!"""

    def __init__(self, player: Player = None, faction: Faction = None):
        """
        :param player: Player
        :param faction: Faction -- set this Condition to the CPU-controlled
        Faction to track if all CPU-players were eliminated by the human with
        just one Condition.
        """
        super().__init__(player)
        self.faction = faction

    def is_met(self) -> bool:
        if self.faction is not None:
            return len(self.faction.units) + len(self.faction.buildings) == 0
        return len(self.player.units) + len(self.player.buildings) == 0


class HasUnitsOfType(Condition):

    def __init__(self, player: Player, unit_type, amount=0):
        super().__init__(player)
        self.unit_type = unit_type
        self.amount = amount

    def is_met(self) -> bool:
        return sum(1 for u in self.player.units if isinstance(u, self.unit_type)) > self.amount


class HasBuildingsOfType(HasUnitsOfType):
    def __init__(self, player: Player, building_type, amount=0):
        super().__init__(player, building_type, amount)

    def is_met(self) -> bool:
        return sum(1 for u in self.player.buildings if isinstance(u, self.unit_type)) > self.amount


class ControlsBuilding(Condition):
    def __init__(self, player: Player, building_id: int):
        super().__init__(player)
        self.building_id = building_id

    def is_met(self) -> bool:
        return any(b.id == self.building_id for b in self.player.buildings)


class ControlsArea(Condition):

    def is_met(self) -> bool:
        pass


class HasTechnology(Condition):
    def __init__(self, mission, player: Player, technology_id: int):
        super().__init__(player)
        self.technology_id = technology_id

    def is_met(self) -> bool:
        return self.technology_id in self.player.known_technologies


class HasResource(Condition):

    def __init__(self, player: Player, resource: str, amount: int):
        super().__init__(player)
        self.resource = resource
        self.amount = amount

    def is_met(self) -> bool:
        return self.player.has_resource(self.resource, self.amount)


class MinimumVictoryPoints(Condition):

    def __init__(self, player: Player, required_vp: int):
        super().__init__(player)
        self.required_vp = required_vp

    def is_met(self) -> bool:
        return self.mission.victory_points[self.player.id] >= self.required_vp


if __name__ == '__main__':
    from scenarios.missions import Mission
