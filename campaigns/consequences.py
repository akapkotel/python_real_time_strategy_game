#!/usr/bin/env python
from abc import abstractmethod
from typing import Optional

from players_and_factions.player import Player


class Consequence:
    """
    Consequence is an event executed when a Condition to which it is bound, is
    met.
    """

    def __init__(self, player: Optional[Player] = None):
        """
        Attach the Consequence to the Condition by calling it's triggers()
        method and passing the Consequence object as th argument.

        :param player: Optional[Player] -- if this argument is not provided,
        then the Player of the Condition is used. The Consequence will apply to
        this player.
        """
        self.player = player
        self.mission = None

    @abstractmethod
    def execute(self):
        raise NotImplementedError

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.player = self.mission.game.players[self.player]

    def __getstate__(self):
        state = self.__dict__.copy()
        state['player'] = self.player.id
        return state


class AddVictoryPoints(Consequence):

    def __init__(self, player: Optional[Player] = None, amount: int = 1):
        super().__init__(player)
        self.amount = amount

    def execute(self):
        self.mission.add_victory_points(self.player, self.amount)


class Defeat(Consequence):
    """
    Set it as a consequence of a Condition to trigger player defeat. The player
    would be removed from the current game.
    """

    def execute(self):
        self.mission.eliminate_player(self.player)


class Victory(Consequence):
    """Set it as a consequence of a Condition to trigger player's victory."""
    def __init__(self, player: Optional[Player] = None):
        super().__init__(player)

    def execute(self):
        self.mission.end_mission(winner=self.player)
