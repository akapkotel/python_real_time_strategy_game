#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod

from players_and_factions.player import Player, Faction


class EventTrigger:
    """EventTrigger is used for TriggeredEvents to control if they should happen."""

    def __init__(self, player: Player):
        self.player = player
        self.game = self.player.game
        self.active = True

    def __str__(self):
        return f'{self.__class__.__name__} for player: {self.player}'

    @abstractmethod
    def condition_fulfilled(self) -> bool:
        raise NotImplementedError

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.player = self.game.players[self.player]

    def __getstate__(self):
        state = self.__dict__.copy()
        state['player'] = self.player.id
        return state


class PlayerSelectedUnitsTrigger(EventTrigger):

    def __init__(self, player: Player, *units_to_select_names: str):
        super().__init__(player)
        self.units_to_select_names = units_to_select_names

    def condition_fulfilled(self) -> bool:
        if not self.units_to_select_names:
            return len(self.game.units_manager.selected_units) > 0


class PlayerSelectedBuildingTrigger(EventTrigger):

    def __init__(self, player: Player, building_to_select_name: str):
        super().__init__(player)
        self.building_to_select_name = building_to_select_name

    def condition_fulfilled(self) -> bool:
        return self.game.units_manager.selected_building.object_name == self.building_to_select_name


class TimePassedTrigger(EventTrigger):

    def __init__(self, player: Player, required_time: int):
        super().__init__(player)
        self.required_time = required_time

    def condition_fulfilled(self) -> bool:
        return self.game.timer.minutes >= self.required_time

    def __getstate__(self):
        saved = super().__getstate__()
        saved['required_time'] = self.required_time
        return saved

    def __setstate__(self, state):
        super().__setstate__(state)


class MapRevealedTrigger(EventTrigger):
    def condition_fulfilled(self) -> bool:
        return len(self.game.fog_of_war.unexplored) == 0


class NoUnitsLeftTrigger(EventTrigger):
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

    def condition_fulfilled(self) -> bool:
        if self.faction is not None:
            return not (self.faction.units or self.faction.buildings)
        return not (self.player.units or self.player.buildings)

    def __setstate__(self, state):
        super().__setstate__(state)
        self.faction = None if self.faction is None else self.player.faction

    def __getstate__(self):
        state = super().__getstate__()
        return state


class HasUnitsOfTypeTrigger(EventTrigger):

    def __init__(self, player: Player, unit_type: str, amount=0):
        super().__init__(player)
        self.unit_type = unit_type.strip('.png')
        self.amount = amount

    def condition_fulfilled(self) -> bool:
        return sum(1 for u in self.player.units if self.unit_type in u.object_name) > self.amount


class HasBuildingsOfTypeCondition(HasUnitsOfTypeTrigger):
    def __init__(self, player: Player, building_type, amount=0):
        super().__init__(player, building_type, amount)

    def condition_fulfilled(self) -> bool:
        return sum(1 for u in self.player.buildings if self.unit_type in u.object_name) > self.amount


class ControlsBuildingTrigger(EventTrigger):
    def __init__(self, player: Player, building_id: int):
        super().__init__(player)
        self.building_id = building_id

    def condition_fulfilled(self) -> bool:
        return any(b.id == self.building_id for b in self.player.buildings)


class ControlsAreaTrigger(EventTrigger):

    def condition_fulfilled(self) -> bool:
        pass


class HasTechnologyTrigger(EventTrigger):
    def __init__(self, scenario, player: Player, technology_id: int):
        super().__init__(player)
        self.technology_id = technology_id

    def condition_fulfilled(self) -> bool:
        return self.technology_id in self.player.known_technologies


class HasResourceTrigger(EventTrigger):

    def __init__(self, player: Player, resource: str, amount: int):
        super().__init__(player)
        self.resource = resource
        self.amount = amount

    def condition_fulfilled(self) -> bool:
        return self.player.has_resource(self.resource, self.amount)


class VictoryPointsTrigger(EventTrigger):

    def __init__(self, player: Player, required_vp: int):
        super().__init__(player)
        self.required_vp = required_vp

    def condition_fulfilled(self) -> bool:
        return self.game.current_mission.victory_points[self.player.id] >= self.required_vp
