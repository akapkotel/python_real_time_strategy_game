#!/usr/bin/env python

from abc import abstractmethod

from players_and_factions.player import Player


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


class Condition:
    """
    Condition is a flag-class checked against, to evaluate if any of the
    Players achieved his objectives.
    """

    def __init__(self, mission, player: Player, consequence: Consequence):
        self.name = self.__class__.__name__
        self.player = player
        self.mission = mission
        self.consequence = self._add_consequence(consequence)

    def _add_consequence(self, consequence: Consequence) -> Consequence:
        consequence.player = self.player
        consequence.mission = self.mission
        return consequence

    @abstractmethod
    def is_met(self) -> bool:
        raise NotImplementedError

    def execute_consequences(self):
        self.consequence.execute()


class TimePassed(Condition):

    def __init__(self, mission, player: Player, required_time: int, consequence):
        super().__init__(mission, player, consequence)
        self.required_time = required_time

    def is_met(self) -> bool:
        return self.mission.game.timer['m'] >= self.required_time


class MapRevealed(Condition):
    def is_met(self) -> bool:
        return len(self.mission.game.fog_of_war.unexplored) == 0


class NoUnitsLeft(Condition):
    def is_met(self) -> bool:
        return len(self.player.units) == 0


class HasUnitsOfType(Condition):

    def __init__(self, mission, player: Player, consequence, unit_type, amount=0):
        super().__init__(mission, player, consequence)
        self.unit_type = unit_type
        self.amount = amount

    def is_met(self) -> bool:
        return sum(1 for u in self.player.units if isinstance(u, self.unit_type)) > self.amount


class HasBuildingsOfType(HasUnitsOfType):
    def __init__(self, mission, player: Player, consequence, building_type, amount=0):
        super().__init__(mission, player, consequence, building_type, amount)

    def is_met(self) -> bool:
        return sum(1 for u in self.player.buildings if isinstance(u, self.unit_type)) > self.amount


class ControlsBuilding(Condition):
    def __init__(self, mission, player: Player, building_id: int, consequence):
        super().__init__(mission, player, consequence)
        self.building_id = building_id

    def is_met(self) -> bool:
        return any(b.id == self.building_id for b in self.player.buildings)


class ControlsArea(Condition):

    def is_met(self) -> bool:
        pass


class HasTechnology(Condition):
    def __init__(self, mission, player: Player, technology_id: int, consequence):
        super().__init__(mission, player, consequence)
        self.technology_id = technology_id

    def is_met(self) -> bool:
        return self.technology_id in self.player.known_technologies


class HasResource(Condition):

    def __init__(self, mission, player: Player, resource: str, amount: int, consequence):
        super().__init__(mission, player, consequence)
        self.resource = resource
        self.amount = amount

    def is_met(self) -> bool:
        return self.player.has_resource(self.resource, self.amount)


class MinimumVictoryPoints(Condition):

    def __init__(self, mission, player: Player, required_vp: int, consequence):
        super().__init__(mission, player, consequence)
        self.required_vp = required_vp

    def is_met(self) -> bool:
        return self.mission.victory_points[self.player.id] >= self.required_vp
