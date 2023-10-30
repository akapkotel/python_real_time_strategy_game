#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Optional, List, Dict

from players_and_factions.player import Player


class Event:
    """Event is executed when its Trigger is fired."""

    def __init__(self, player: Player):
        self.player = player
        self.scenario = None
        self.active = True

    @abstractmethod
    def execute(self):
        raise NotImplementedError

    def save(self) -> Dict:
        return {
            'class_name': self.__class__.__name__,
            'player': self.player.id,
        }

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.player = self.scenario.game.players[self.player]

    def __getstate__(self):
        state = self.__dict__.copy()
        state['player'] = self.player.id
        state['scenario'] = None
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
