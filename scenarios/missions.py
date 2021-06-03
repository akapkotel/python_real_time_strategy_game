#!/usr/bin/env python
from __future__ import annotations

from typing import List, Dict

from utils.logging import log
from .conditions import Condition
from players_and_factions.player import Player


class Mission:
    """
    Mission keeps track of the scenario-objectives and evaluates if Players
    achieved their objectives and checks win and fail conditions. It allows to
    control when the current game ends and what is the result of a game.
    """
    game = None

    def __init__(self, id: int, name: str, map_name: str):
        self.id = id
        self.name = name
        self.map_name = map_name
        self.conditions: List[Condition] = []
        self.victory_points: Dict[int, int] = {}
        self.required_victory_points: Dict[int, int] = {}

    def new_condition(self):
        raise NotImplementedError

    def remove_condition(self):
        raise NotImplementedError

    def update(self):
        self.evaluate_conditions()
        self.check_victory_points()

    def evaluate_conditions(self):
        for condition in (c for c in self.conditions if c.is_met()):
            condition.execute_consequences()
            self.conditions.remove(condition)

    def check_victory_points(self):
        for index, points in self.victory_points.items():
            if points >= self.required_victory_points[index]:
                return self.end_mission(winner=self.game.players[index])

    def end_mission(self, winner: Player):
        log(f'Player: {winner} has won in {winner}!')
        self.game.toggle_pause()
