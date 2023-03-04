#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from players_and_factions.player import Player, Faction
from campaigns.triggered_events import AddVictoryPoints, TriggeredEvent
from utils.game_logging import log


class Trigger:
    """
    Trigger is a flag-class checked against, to evaluate if any of the
    Players achieved his objectives. You can use them as events also.
    """

    def __init__(self, player: Player, optional: bool = False):
        self.name = self.__class__.__name__
        self.player = player
        self.mission: Optional[Mission] = None
        self.optional = optional
        self.victory_points = 0
        self._triggered_events = []

    def __str__(self):
        return f'{self.__class__.__name__} for player: {self.player}'

    def set_vp(self, value: int) -> Trigger:
        self.victory_points = value
        self.add_triggered_event(AddVictoryPoints(self.player, value))
        return self

    def triggers(self, *triggered_events: TriggeredEvent) -> Trigger:
        """
        Use this method to attach TriggeredEvents to this Trigger object. Use:
        trigger.triggers(TriggeredEvent())

        :param triggered_events: Tuple[TriggeredEvent] -- you can pass as many
        TriggeredEvent objects as you want. They execute() method would be called
        when is_met() method of this class is called.
        :return: Trigger -- this object to allow chaining
        """
        for triggered in triggered_events:
            self.add_triggered_event(triggered)
        return self

    def bind_mission(self, mission: Mission) -> Trigger:
        self.mission = mission
        for consequence in (c for c in self._triggered_events if c.mission is None):
            consequence.mission = mission
        return self

    def add_triggered_event(self, triggered_event: TriggeredEvent) -> Trigger:
        if triggered_event.player is None:
            triggered_event.player = self.player
        self._triggered_events.append(triggered_event)
        return self

    @abstractmethod
    def fulfilled(self) -> bool:
        raise NotImplementedError

    def execute_triggered_events(self):
        for triggered_event in self._triggered_events:
            triggered_event.execute()
            log(f'Trigger {self} was executed!', console=True)

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.player = self.mission.game.players[self.player]

    def __getstate__(self):
        state = self.__dict__.copy()
        state['player'] = self.player.id
        return state


class TimePassedTrigger(Trigger):

    def __init__(self, player: Player, required_time: int):
        super().__init__(player)
        self.required_time = required_time

    def fulfilled(self) -> bool:
        return self.mission.game.timer.minutes >= self.required_time

    def __getstate__(self):
        saved = super().__getstate__()
        saved['required_time'] = self.required_time
        return saved

    def __setstate__(self, state):
        super().__setstate__(state)


class MapRevealedTrigger(Trigger):
    def fulfilled(self) -> bool:
        return len(self.mission.game.fog_of_war.unexplored) == 0


class NoUnitsLeftTrigger(Trigger):
    """Beware that this Trigger checks bot against Units and Buildings!"""

    def __init__(self, player: Player = None, faction: Faction = None):
        """
        :param player: Player
        :param faction: Faction -- set this Trigger to the CPU-controlled
        Faction to track if all CPU-players were eliminated by the human with
        just one Trigger.
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


class HasUnitsOfTypeTrigger(Trigger):

    def __init__(self, player: Player, unit_type: str, amount=0):
        super().__init__(player)
        self.unit_type = unit_type.strip('.png')
        self.amount = amount

    def fulfilled(self) -> bool:
        return sum(1 for u in self.player.units if self.unit_type in u.object_name) > self.amount


class HasBuildingsOfTypeCondition(HasUnitsOfTypeTrigger):
    def __init__(self, player: Player, building_type, amount=0):
        super().__init__(player, building_type, amount)

    def fulfilled(self) -> bool:
        return sum(1 for u in self.player.buildings if self.unit_type in u.object_name) > self.amount


class ControlsBuildingTrigger(Trigger):
    def __init__(self, player: Player, building_id: int):
        super().__init__(player)
        self.building_id = building_id

    def fulfilled(self) -> bool:
        return any(b.id == self.building_id for b in self.player.buildings)


class ControlsAreaTrigger(Trigger):

    def fulfilled(self) -> bool:
        pass


class HasTechnologyTrigger(Trigger):
    def __init__(self, mission, player: Player, technology_id: int):
        super().__init__(player)
        self.technology_id = technology_id

    def fulfilled(self) -> bool:
        return self.technology_id in self.player.known_technologies


class HasResourceTrigger(Trigger):

    def __init__(self, player: Player, resource: str, amount: int):
        super().__init__(player)
        self.resource = resource
        self.amount = amount

    def fulfilled(self) -> bool:
        return self.player.has_resource(self.resource, self.amount)


class VictoryPointsTrigger(Trigger):

    def __init__(self, player: Player, required_vp: int):
        super().__init__(player)
        self.required_vp = required_vp

    def fulfilled(self) -> bool:
        return self.mission.victory_points[self.player.id] >= self.required_vp


if __name__ == '__main__':
    from campaigns.missions import Mission
