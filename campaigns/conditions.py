#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from players_and_factions.player import Player, Faction
from campaigns.consequences import AddVictoryPoints, Consequence
from utils.game_logging import log


class Condition:
    """
    Condition is a flag-class checked against, to evaluate if any of the
    Players achieved his objectives. You can use them as events also.
    """

    def __init__(self, player: Player, optional: bool = False):
        self.name = self.__class__.__name__
        self.player = player
        self.mission: Optional[Mission] = None
        self.optional = optional
        self.victory_points = 0
        self._consequences = []

    def __str__(self):
        return f'{self.__class__.__name__} for player: {self.player}'

    def set_vp(self, value: int) -> Condition:
        self.victory_points = value
        self.add_consequence(AddVictoryPoints(self.player, value))
        return self

    def triggers(self, *consequences: Consequence) -> Condition:
        """
        Use this method to attach Consequences to this Condition object. Use:
        condition.triggers(Consequence())

        :param consequences: Tuple[Consequence] -- you can pass as many
        Consequence objects as you want. They execute() method would be called
        when is_met() method of this class is called.
        :return: Condition -- this object to allow chaining
        """
        for consequence in consequences:
            self.add_consequence(consequence)
        return self

    def bind_mission(self, mission: Mission) -> Condition:
        self.mission = mission
        for consequence in (c for c in self._consequences if c.mission is None):
            consequence.mission = mission
        return self

    def add_consequence(self, consequence: Consequence) -> Condition:
        if consequence.player is None:
            consequence.player = self.player
        self._consequences.append(consequence)
        return self

    @abstractmethod
    def fulfilled(self) -> bool:
        raise NotImplementedError

    def execute_consequences(self):
        for consequence in self._consequences:
            consequence.execute()
            log(f'Condition {self} was met!', console=True)

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.player = self.mission.game.players[self.player]

    def __getstate__(self):
        state = self.__dict__.copy()
        state['player'] = self.player.id
        return state


class TimePassedCondition(Condition):

    def __init__(self, player: Player, required_time: int):
        super().__init__(player)
        self.required_time = required_time

    def fulfilled(self) -> bool:
        return self.mission.game.timer.minutes >= self.required_time
        # return self.mission.game.timer['m'] >= self.required_time

    def __getstate__(self):
        saved = super().__getstate__()
        saved['required_time'] = self.required_time
        return saved

    def __setstate__(self, state):
        super().__setstate__(state)


class MapRevealedCondition(Condition):
    def fulfilled(self) -> bool:
        return len(self.mission.game.fog_of_war.unexplored) == 0


class NoUnitsLeftCondition(Condition):
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

    def fulfilled(self) -> bool:
        if self.faction is not None:
            return not (self.faction.units or self.faction.buildings)
        return not (self.player.units or self.player.buildings)

    def __setstate__(self, state):
        super().__setstate__(state)
        self.faction = None if self.faction is None else self.player.faction

    def __getstate__(self):
        state = super().__getstate__()
        return state


class HasUnitsOfTypeCondition(Condition):

    def __init__(self, player: Player, unit_type: str, amount=0):
        super().__init__(player)
        self.unit_type = unit_type.strip('.png')
        self.amount = amount

    def fulfilled(self) -> bool:
        return sum(1 for u in self.player.units if self.unit_type in u.object_name) > self.amount


class HasBuildingsOfTypeCondition(HasUnitsOfTypeCondition):
    def __init__(self, player: Player, building_type, amount=0):
        super().__init__(player, building_type, amount)

    def fulfilled(self) -> bool:
        return sum(1 for u in self.player.buildings if self.unit_type in u.object_name) > self.amount


class ControlsBuildingCondition(Condition):
    def __init__(self, player: Player, building_id: int):
        super().__init__(player)
        self.building_id = building_id

    def fulfilled(self) -> bool:
        return any(b.id == self.building_id for b in self.player.buildings)


class ControlsAreaCondition(Condition):

    def fulfilled(self) -> bool:
        pass


class HasTechnologyCondition(Condition):
    def __init__(self, mission, player: Player, technology_id: int):
        super().__init__(player)
        self.technology_id = technology_id

    def fulfilled(self) -> bool:
        return self.technology_id in self.player.known_technologies


class HasResourceCondition(Condition):

    def __init__(self, player: Player, resource: str, amount: int):
        super().__init__(player)
        self.resource = resource
        self.amount = amount

    def fulfilled(self) -> bool:
        return self.player.has_resource(self.resource, self.amount)


class VictoryPointsCondition(Condition):

    def __init__(self, player: Player, required_vp: int):
        super().__init__(player)
        self.required_vp = required_vp

    def fulfilled(self) -> bool:
        return self.mission.victory_points[self.player.id] >= self.required_vp


if __name__ == '__main__':
    from campaigns.missions import Mission
