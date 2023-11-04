#!/usr/bin/env python
from __future__ import annotations

import random
from math import dist
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from utils.game_logging import log_here

from arcade import load_sound, play_sound, stop_sound, Sound
from pyglet.media import Player


SOUNDS_DIRECTORY = 'resources/sounds'
SOUNDS_EXTENSION = 'wav'
MUSIC_TRACK_SUFFIX = 'theme'
UNITS_MOVE_ORDERS_CONFIRMATIONS = [f'on_unit_get_order_{i}.wav' for i in range(6)]
UNITS_SELECTION_CONFIRMATIONS = [f'on_unit_selected_{i}.wav' for i in range(6)]
UNIT_PRODUCTION_FINISHED = [f'unit_{suffix}.wav' for suffix in ("ready", "complete")]


class SoundPlayer:
    window = None
    game = None
    instance = None

    def __init__(self, window):
        """
        SoundPlayer manages and plays sounds, and music in game.

        :param window: GameWindow
        :param sound_on: bool -- if sounds should be played or not
        :param music_on: bool -- if music should be played or not
        :param sound_effects_on: bool -- if sound effects should be played or not
        """
        self.window = window
        self._sound_on = window.settings.sound_on
        self._music_on = window.settings.music_on
        self._sound_effects_on = window.settings.sound_effects_on

        self._sound_volume: float = window.settings.sound_volume
        self._music_volume: float = window.settings.music_volume
        self._effects_volume: float = window.settings.effects_volume

        self.sounds: Dict[str, Sound] = self._preload_sounds()
        self.currently_played: List[Player] = []
        self.current_music: Optional[Player] = None

        self.paused_track_name: Optional[str] = None
        self.paused_track_time: Optional[float] = None

        self.playlists: Dict[str, List[str]] = self._setup_playlists()
        self.current_playlist: Optional[List[str]] = None
        self.playlist_index: int = 0

        self.max_sound_distance: Optional[float] = None

        SoundPlayer.instance = self

        log_here(f'Loaded {len(self.sounds)} sounds.', console=True)
        log_here(f'Found {len(self.playlists)} playlists', console=True)

    def _preload_sounds(self) -> Dict[str, Sound]:
        names_to_paths = self.window.resources_manager.get(SOUNDS_EXTENSION)
        return {
            name: load_sound(path, streaming=False) for
            name, path in names_to_paths.items()
        }

    def _setup_playlists(self) -> Dict[str, List[str]]:
        playlists = defaultdict(list)
        for sound_name in (s for s in self.sounds.keys() if self.is_music(s)):
            playlist_name = sound_name.partition('_')[0]
            playlists[playlist_name].append(sound_name)
        return playlists

    @staticmethod
    def is_music(sound_name: str) -> bool:
        return MUSIC_TRACK_SUFFIX in sound_name

    @property
    def sound_on(self) -> bool:
        return self._sound_on

    @sound_on.setter
    def sound_on(self, value: bool):
        self._sound_on = self.window.settings.sound_on = value
        self.pause_or_resume_playing_music()

    @property
    def music_on(self) -> bool:
        return self._sound_on and self._music_on

    @music_on.setter
    def music_on(self, value: bool):
        self._music_on = self.window.settings.music_on = value
        self.pause_or_resume_playing_music()

    def pause_or_resume_playing_music(self):
        if self.music_on and self.paused_track_name is not None:
            self._resume_playing_paused_music_track()
        else:
            self._pause_current_music_track()

    @property
    def sound_effects_on(self):
        return self._sound_on and self._sound_effects_on

    @sound_effects_on.setter
    def sound_effects_on(self, value: bool):
        self._sound_effects_on = self.window.settings.sound_effects_on = value * 2

    @property
    def sound_volume(self):
        return self._sound_volume

    @sound_volume.setter
    def sound_volume(self, value: float):
        self._sound_volume = self.window.settings.sound_volume = value
        self.pause_or_resume_playing_music()

    @property
    def music_volume(self):
        return self._sound_volume * self._music_volume

    @music_volume.setter
    def music_volume(self, value: float):
        self._music_volume = self.window.settings.music_volume = value
        self.pause_or_resume_playing_music()

    @property
    def effects_volume(self):
        return self._sound_volume * self._effects_volume

    @effects_volume.setter
    def effects_volume(self, value: float):
        self._effects_volume = self.window.settings.effects_volume = value

    def _pause_current_music_track(self):
        self.paused_track_time = self.current_music.time
        self.paused_track_name = self._current_track_name()
        self.current_music.pause()

    def _resume_playing_paused_music_track(self):
        self.play_music(self.paused_track_name, False)
        self.current_music.seek(self.paused_track_time)

    def _current_track_name(self) -> str:
        return self.current_playlist[self.playlist_index]

    def on_update(self):
        if self.max_sound_distance is None and self.game is not None and self.game.is_running:
            self.max_sound_distance = dist((0, 0), (self.game.map.width, self.game.map.height))
        if self.current_music is not None and not self.current_music.playing:
            if (playlist := self.current_playlist) is not None:
                self._next_playlist_index()
                self.play_music(playlist[self.playlist_index], False)

    def _next_playlist_index(self):
        if self.playlist_index == len(self.current_playlist) - 1:
            self.playlist_index = 0
        else:
            self.playlist_index += 1

    def play_playlist(self, playlist_name: str):
        if (playlist := self.playlists.get(playlist_name, None)) is not None:
            self._stop_music_track()
            self.current_playlist = playlist
            self.playlist_index = 0
            self.play_music(self.current_playlist[self.playlist_index], False)

    def play_sound(self, name: str, volume: Optional[float]=None, sound_position: Optional[Tuple[float, float]]=None):
        """Play a single sound. Use this for sound effects."""
        if name not in self.sounds:
            log_here(f'Sound: {name} not found!', console=True)
            return
        elif self.is_music(name) and not self.music_on:
            return
        elif not self.sound_effects_on:
            return

        if volume is None and sound_position is not None and self.max_sound_distance is not None:
            volume = self.calculate_volume_based_on_distance(sound_position)

        self._play_sound(name, loop=False, volume=volume)

    def calculate_volume_based_on_distance(self, sound_position: Tuple[float, float]) -> float:
        """
        The loudest sounds are played when camera is positioned on the position, where sound was emitted in game-world.
        As the distance of current player viewport from that position raises, sound volume drops.
        """
        viewport = self.game.viewport
        player_position = (viewport[0] + viewport[1] / 2, viewport[2] + viewport[3] / 2)
        return 1 - dist(sound_position, player_position) / self.max_sound_distance

    def play_music(self, name: str, loop=True, volume: Optional[float] = None):
        """Use this for background sound-themes."""
        if self.current_music is not None:
            self._stop_music_track()
        if self.music_on:
            self._play_music_track(name, loop, volume or self.music_volume)

    def play_random_sound(self, sounds_list: List[str], volume: Optional[float] = None):
        """Play sound randomly chosen from list of sounds names."""
        self.play_sound(random.choice(sounds_list), volume or self.effects_volume)

    def _stop_music_track(self):
        try:
            stop_sound(self.current_music)
        except (AttributeError, ValueError):
            pass
        finally:
            self.current_music = None

    def _play_music_track(self, name, loop, volume):
        # volume = self.music_volume * volume if volume is not None else self.music_volume
        player = self._get_player(name, loop, volume)
        self.current_music = player

    def _play_sound(self, name, loop, volume):
        volume = self.effects_volume * volume if volume is not None else self.effects_volume
        player = self._get_player(name, loop, volume)
        self.currently_played.append(player)

    def _get_player(self, name, loop, volume) -> Player:
        volume = min(volume, self.sound_volume)
        return play_sound(self.sounds[name], volume, looping=loop)

    def play(self):
        """Plays all the sounds."""
        self.music_on = True
        for player in self.currently_played:
            player.play()

    def pause(self):
        """Pauses playing all the sounds."""
        self.music_on = False
        for player in self.currently_played:
            player.pause()
