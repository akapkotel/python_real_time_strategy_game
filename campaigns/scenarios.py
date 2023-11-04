#!/usr/bin/env python
from __future__ import annotations

import os
import shelve

from campaigns.triggers import EventTrigger
from utils.colors import CLEAR_GREEN, RED

from typing import List, Set, Dict
from collections import namedtuple, defaultdict

from utils.functions import find_paths_to_all_files_of_type
from utils.scheduling import ScheduledEvent
from campaigns.research import Technology
from players_and_factions.player import Player

ScenarioDescriptor = namedtuple('ScenarioDescriptor',
                                ['name',
                                 'finished',
                                'campaign_name',
                                'map_name',
                                'triggers',
                                'description'])


class Scenario:
    """
    Scenario keeps track of TriggeredEvents checking if any of them should be executed.
    """
    game = None

    def __init__(self, scenario_name: str, map_name: str, campaign_name: str = None, index: int = 0):
        self.scenario_name = scenario_name
        self.campaign_name = campaign_name
        self.finished = False
        self.description = ''
        self.map_name = map_name
        self.index = index

        self.players: Set[int] = set()
        self.start_resources: Dict[int, Dict[str, int]] = {}
        self.allowed_technologies: Dict[int, Dict[int, Technology]] = {}
        self.victory_points: Dict[int, int] = defaultdict(int)
        self.required_victory_points: Dict[int, int] = defaultdict(int)

        self.events_triggers: List[EventTrigger] = []

        self.ended = False
        self.winner = None

        self.game.schedule_event(ScheduledEvent(self, 1, self.evaluate_events_triggers, repeat=-1))

    @property
    def is_playable(self) -> bool:
        if self.campaign_name is not None:
            return self.scenario_name in self.campaign.playable_missions
        return not self.campaign_name

    @property
    def campaign(self) -> Campaign:
        return self.game.window.campaigns[self.campaign_name]

    @property
    def get_descriptor(self) -> ScenarioDescriptor:
        return ScenarioDescriptor(
            self.scenario_name,
            self.finished,
            self.campaign_name,
            self.map_name,
            [],  # TODO: convert self.triggers to readable, safe format
            self.description
        )

    def unlock_technologies_for_player(self, player: Player, *technologies: str) -> Scenario:
        for tech_name in technologies:
            tech_data = self.game.configs[tech_name]
            technology = Technology(*[d for d in list(tech_data.values())[4:]])
            self.allowed_technologies[player.id][technology.id] = technology
        return self

    def unlock_buildings_for_player(self, player: Player, *buildings: str) -> Scenario:
        player.buildings_possible_to_build.extend(buildings)
        return self

    def add_events_triggers(self, *events_triggers: EventTrigger) -> Scenario:
        for trigger in events_triggers:
            self.events_triggers.append(trigger)
            trigger.bind_game_and_scenario(self)
        return self

    def add_players(self, *players: Player) -> Scenario:
        for player in players:
            self.players.add(player.id)
            self.allowed_technologies[player.id] = {}
        return self

    def remove_event_trigger(self, event_trigger: EventTrigger) -> Scenario:
        self.events_triggers.remove(event_trigger)
        return self

    def eliminate_player(self, player: Player):
        player.kill()
        self.players.discard(player.id)
        self.remove_event_triggers_for_player(player)
        self.check_for_last_survivor()

    def remove_event_triggers_for_player(self, player):
        for trigger in [t for t in self.events_triggers if t.player == player]:
            self.events_triggers.remove(trigger)

    def check_for_last_survivor(self):
        if len(self.players) == 1:
            winner_id = self.players.pop()
            self.end_scenario(winner=self.game.players[winner_id])

    def update(self):
        ...

    def evaluate_events_triggers(self):
        for event_trigger in (t for t in self.events_triggers if t.active):
            event_trigger.evaluate_condition()

    def add_victory_points(self, player: Player, points: int):
        self.victory_points[player.id] += points
        self.check_victory_points(player.id)

    def check_victory_points(self, player_id: int):
        points = self.victory_points[player_id]
        if points >= self.required_victory_points[player_id] > 0:
            self.end_scenario(winner=self.game.players[player_id])

    def end_scenario(self, winner: Player):
        self.ended = True
        self.winner = winner
        self.notify_player(winner is self.game.local_human_player)

    def notify_player(self, player_won: bool):
        dialog = 'Victory!' if player_won else 'You have been defeated!'
        color = CLEAR_GREEN if player_won else RED
        self.game.toggle_pause(dialog=dialog, color=color)

    def quit_scenario(self):
        if self.campaign_name is not None and self.winner is self.game.local_human_player:
            campaign = self.game.window.campaigns[self.campaign_name]
            campaign.update(finished_scenario=self)
        self.game.window.quit_current_game(ignore_confirmation=True)

    def __setstate__(self, state):
        self.__dict__.update(state)
        for event_trigger in self.events_triggers:
            event_trigger.bind_game_and_scenario(self)

    def __getstate__(self):
        state = self.__dict__.copy()
        state['allowed_technologies'] = {}
        return state


class Campaign:
    """Campaign is a series of consecutive Missions. When player completes the Mission, next Mission is unlocked."""

    def __init__(self, campaign_name: str, missions_names: List[str]):
        self.name = campaign_name
        self.missions: Dict[int, List] = {
            # why 'not i'? first Mission of a Campaign is always playable!
            i: [name, not i] for i, name in enumerate(missions_names)
        }

    @property
    def playable_missions(self) -> List[str]:
        return [name for (name, status) in self.missions.values() if status]

    @property
    def progress(self) -> int:
        if self.playable_missions[1:]:
            return 100 * (len(self.missions) // len(self.playable_missions))
        return 0

    def update(self, finished_scenario: Scenario):
        try:  # unblock next mission of campaign:
            self.missions[finished_scenario.index + 1][1] = True
        except (KeyError, IndexError):
            pass

    def save_campaign(self,):
        scenarios_path = os.path.abspath('scenarios')
        file_name = '.'.join((self.name, 'cmpgn'))
        with shelve.open(os.path.join(scenarios_path, file_name), 'w') as file:
            file[self.name] = self


def load_campaigns() -> Dict[str, Campaign]:
    campaigns: Dict[str, Campaign] = {}
    names = find_paths_to_all_files_of_type('cmpgn', 'scenarios')
    for name, path in names.items():
        with shelve.open(os.path.join(path, name), 'r') as campaign_file:
            campaign_name = name.replace('.cmpgn', '')
            campaigns[campaign_name] = campaign_file[campaign_name]
    return campaigns
