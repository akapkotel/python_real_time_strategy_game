#!/usr/bin/env python
from __future__ import annotations

from utils.colors import CLEAR_GREEN, RED

from typing import List, Dict
from collections import namedtuple, defaultdict

from utils.logging import log
from .conditions import Condition
from players_and_factions.player import Player


MissionDescriptor = namedtuple('MissionDescriptor',
                               ['name',
                                'map_name',
                                'conditions',
                                'description'])


class Mission:
    """
    Mission keeps track of the scenario-objectives and evaluates if Players
    achieved their objectives and checks win and fail conditions. It allows to
    control when the current game ends and what is the result of a game.
    """
    game = None

    def __init__(self, id: int, name: str, map_name: str, campaign: str = None):
        self.id = id
        self.campaign = campaign
        self.name = name
        self.description = ''
        self.map_name = map_name
        self.conditions: List[Condition] = []
        self.victory_points: Dict[int, int] = defaultdict(int)
        self.required_victory_points: Dict[int, int] = defaultdict(int)

    @property
    def get_descriptor(self) -> MissionDescriptor:
        return MissionDescriptor(self.name, self.map_name, self.conditions, self.description)

    def add(self,
            player: Player = None,
            condition: Condition = None,
            optional=False):
        if player is not None:
            self.victory_points[player.id] = 0
            self.required_victory_points[player.id] = 0
        if condition is not None:
            self.new_condition(condition, optional)

    def new_condition(self, condition: Condition, optional=False):
        condition.bind_mission(self)
        self.conditions.append(condition)
        if not optional and condition.victory_points:
            points = condition.victory_points
            self.required_victory_points[condition.player.id] += points

    def remove_condition(self, condition: Condition):
        self.conditions.remove(condition)

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
        player_won = winner is self.game.local_human_player
        if self.campaign is not None and player_won:
            self.update_campaign()
        log(f'Player: {winner} has won!')
        self.notify_player(player_won, winner.name)

    def notify_player(self, player_won, winner_name):
        color = CLEAR_GREEN if player_won else RED
        self.game.toggle_pause(dialog=f'{winner_name} won!', color=color)

    def update_campaign(self):
        # : campaing management after Mission end
        ...
