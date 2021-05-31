#!/usr/bin/env python
from __future__ import annotations

from typing import Optional, List, Set, Tuple, Dict

from arcade import load_texture

from utils.functions import get_path_to_file, get_enemies
from utils.scheduling import log
from players_and_factions.player import Player, CpuPlayer
from map.map import Map


class Event:
    """
    Events are used to control flow of played scenario. They are
    objectives which must be fulfilled to successfully win or to
     loose game. Each Event is evaluated for being fired each
     frame. Events are assigned to Missions.
    """

    game = None  # shared reference to Game

    def __init__(self, index, name, vp, dp, trigger_time, *args, **kwargs):
        self.name = name
        self.id: int = index
        self.victory_point: bool = vp
        self.defeat_point: bool = dp
        self.is_objective: bool = vp + dp > 0
        self.trigger_time: Optional[int] = trigger_time or None

    def __str__(self):
        return f"Event of type: {self.__class__.__name__}"

    def __repr__(self):
        return self.__str__()

    def trigger(self, game_time: int):
        return self.trigger_time is None or self.check_time(game_time)

    def check_time(self, game_time: int) -> bool:
        return self.trigger_time >= game_time

    def __call__(self, *args, **kwargs):
        pass


class Mission:
    """
    This class contains all data required to load and play a single
    scenario. Mission determines which Map will be is_loaded, what objectives
    should Player achieve to win and what are his defeat's conditions. It
    can also determine some scripted events and AI-strategies.
    """
    game = None

    def __init__(self, game, index, name, desc, image_name, map_name, events,
                 fired_events, human_players, cpu_players, civilians, enemies,
                 victory_points, defeat_points, required):
        self.index: int = index
        self.name: str = name
        self.description: str = desc
        image_name = f"ui/missions/{image_name}"
        self.image = load_texture(get_path_to_file(image_name))
        self.map_name: str = map_name
        self.map: Optional[Map] = None
        self.required: Optional[int] = required
        # self.game = game  # type: Game
        self.events_indexes: List[int] = events
        self.events: Optional[Set[Event]] = None
        self.fired_events: Set[Event] = set(fired_events)
        self.human_players: int = human_players
        self.cpu_players: int = cpu_players
        self.civilians: bool = civilians
        self.enemies: Set[Tuple[int, int]] = {get_enemies(e) for e in enemies}
        self.victory_points: List[int] = [victory_points, 0]  # [required, current]
        self.defeat_points: List[int] = [defeat_points, 0]
        self.finished: bool = self.check_if_finished()

    def check_if_finished(self):
        return self.index in self.game.finished_missions

    def spawn_players(self) -> Dict[int, Player]:
        """
        Build dict of Player instances. Each Player is mapped to integer key,
        similar  it's id property. Players id's (indexes) begin from 2 and are
        consecutive powers of 2, what allows for easy calculation of indexes
        from their sums (eg. 258 = 256 + 2) what is usefull to save and load
        pairs of enemies from missions.cfg files. See functions.get_enemies()
        functions in helpers module.
        """
        players = {}
        index = 2  # first human Player has always index 2
        # human players:
        for i in range(self.human_players):
            players[index] = Player(index, )
            index = index << 1
        # cpu-players:
        for i in range(self.cpu_players):
            players[index] = CpuPlayer(index)
            index = index << 1
        # cpu-civilian player:
        if self.civilians:
            players[index] = CpuPlayer(index)
        for player in players.values():
            player.detected_enemies = {p: {} for p in players if players[p] != player}
        return players

    def get_enemies_for_player(self, index: int) -> Set[int]:
        enemies: Set[int] = set()
        for war in (w for w in self.enemies if index in w):
            enemies.add([e for e in war if e != index].pop())
        return enemies

    def update(self, game_time: int):
        """
        :param game_time: int -- seconds after Mission start
        """
        for event in (e for e in self.events if e.trigger(game_time)):
            if event.is_objective:
                self.add_victory_and_defeat_points(event)
            log(f"{event} was triggered")
            self.fired_events.add(event)
            event()
        self.check_for_victory_and_defeat()
        self.events -= self.fired_events

    def add_victory_and_defeat_points(self, event: Event):
        self.victory_points[1] += event.victory_point
        self.defeat_points[1] += event.defeat_point

    def check_for_victory_and_defeat(self):
        if self.victory_points[0] == self.victory_points[1]:
            self.end_mission(player_wins=True)
        elif self.defeat_points[0] == self.defeat_points[1]:
            self.end_mission(player_wins=False)

    def end_mission(self, player_wins: bool):
        if player_wins:
            self.finished = True
            log(f"Mission {self.name} was successfully finished!")
        else:
            log(f"Player was defeated in mission {self.name}!")
        # TODO: win or loose dialog for player
        self.game.toggle_game_pause()

    def __getstate__(self):
        mission_data = self.__dict__.copy()
        for k, v in mission_data.items():
            print(k, v)
        # del mission_data['game']
        mission_data['image'] = None
        mission_data['map'] = None
        return mission_data

    def __setstate__(self, state):
        self.__dict__.update(state)

