#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Optional, List

from campaigns.triggers import EventTrigger
from players_and_factions.player import Player


class Event:
    """Event is executed when its TriggerEvent is fired."""

    def __init__(self, player: Player):
        self.player = player
        self.scenario = None
        self.active = True
        self.triggers: List[EventTrigger] = []

    def bind_scenario(self, scenario):
        self.scenario = scenario

    def add_triggers(self, *triggers: EventTrigger) -> Event:
        for trigger in (t for t in triggers if t.active):
            self.triggers.append(trigger)
        return self

    def update(self):
        if self.should_be_triggered():
            self.execute()

    def should_be_triggered(self) -> bool:
        return any(trigger.condition_fulfilled() for trigger in self.triggers)

    @abstractmethod
    def execute(self):
        raise NotImplementedError

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.player = self.scenario.game.players[self.player]

    def __getstate__(self):
        state = self.__dict__.copy()
        state['player'] = self.player.id
        return state


class ShowDialog(Event):

    def execute(self):
        self.scenario.game.show_dialog(self)


class Victory(Event):

    def execute(self):
        self.scenario.end_scenario(winner=self.player)


class AddVictoryPoints(Event):

    def __init__(self, player: Optional[Player] = None, amount: int = 1):
        super().__init__(player)
        self.amount = amount

    def execute(self):
        self.scenario.add_victory_points(self.player, self.amount)


class Defeat(Event):

    def execute(self):
        self.scenario.eliminate_player(self.player)
