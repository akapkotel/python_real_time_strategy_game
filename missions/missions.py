#!/usr/bin/env python
from __future__ import annotations

from functools import singledispatchmethod

from utils.colors import CLEAR_GREEN, RED

from typing import List, Set, Dict
from collections import namedtuple, defaultdict

from .conditions import Condition
from players_and_factions.player import Player
from .research import Technology

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

    def __init__(self, name: str, map_name: str, campaign: Campaign = None, index: int = 0):
        self.index = index  # index in campaign missions dict
        self.campaign = campaign
        self.name = name
        self.description = ''
        self.map_name = map_name
        self.conditions: List[Condition] = []
        self.players: Set[int] = set()
        self.allowed_technologies: Dict[int, Dict[int, Technology]] = {}
        self.victory_points: Dict[int, int] = defaultdict(int)
        self.required_victory_points: Dict[int, int] = defaultdict(int)
        self.ended = False
        self.winner = None

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getstate__(self) -> Dict:
        state = self.__dict__.copy()
        return state

    @property
    def get_descriptor(self) -> MissionDescriptor:
        return MissionDescriptor(self.name, self.map_name, self.conditions, self.description)

    def unlock_technologies_for_player(self, player: Player, *technologies: str):
        for tech_name in technologies:
            tech_data = self.game.configs['technologies'][tech_name]
            _class = eval(tech_data['class'])
            technology = _class(*[d for d in list(tech_data.values())[3:]])
            self.allowed_technologies[player.id][technology.id] = technology

    @singledispatchmethod
    def extend(self, *items):
        raise TypeError(f'Unknown items. Accepted are: Condition, Player')

    @extend.register
    def _(self, *items: Condition):
        for condition in items:
            condition.bind_mission(self)
            self.conditions.append(condition)
            if not condition.optional and (points := condition.victory_points):
                self.required_victory_points[condition.player.id] += points

    @extend.register
    def _(self, *items: Player):
        for player in items:
            self.players.add(player.id)
            self.victory_points[player.id] = 0
            self.required_victory_points[player.id] = 0
            self.allowed_technologies[player.id] = {}

    def remove_condition(self, condition: Condition):
        self.conditions.remove(condition)

    def eliminate_player(self, player: Player):
        player.kill()
        self.players.discard(player.id)
        self.check_for_last_survivor()

    def check_for_last_survivor(self):
        if len(self.players) == 1:
            self.end_mission(winner=self.game.players[self.players.pop()])

    def update(self):
        self.evaluate_conditions()

    def evaluate_conditions(self):
        for condition in (c for c in self.conditions if c.is_met()):
            condition.execute_consequences()
            self.conditions.remove(condition)

    def add_victory_points(self, player: Player, points: int):
        self.victory_points[player.id] += points
        self.check_victory_points(player.id)

    def check_victory_points(self, player_id: int):
        points = self.victory_points[player_id]
        if points >= self.required_victory_points[player_id] > 0:
            self.end_mission(winner=self.game.players[player_id])

    def end_mission(self, winner: Player):
        self.ended = True
        self.winner = winner
        self.notify_player(winner is self.game.local_human_player)

    def notify_player(self, player_won: bool):
        if player_won:
            self.game.toggle_pause(dialog='Victory!', color=CLEAR_GREEN)
        else:
            self.game.toggle_pause(dialog='You have been defeated!', color=RED)

    def quit_mission(self):
        if self.campaign is not None and self.winner is self.game.local_human_player:
            self.campaign.update(finished_mission=self)
        self.game.window.show_view(self.game.window.menu_view)
        self.game.window.quit_current_game(ignore_confirmation=True)


class Campaign:

    def __init__(self, missions: List[str]):
        self.name = None
        self.missions: Dict[int, List] = {  # [str: name, bool: if unblocked]
            i: [mission_name, not i] for i, mission_name in enumerate(missions)
        }

    def update(self, finished_mission: Mission):
        try:  # unblock next mission of campaign:
            self.missions[finished_mission.index + 1][1] = True
        except (KeyError, IndexError):
            pass


class CampaignManager:
    # TODO
    pass
