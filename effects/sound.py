#!/usr/bin/env python
from __future__ import annotations

import random
from typing import Dict, List, Optional
from collections import defaultdict

from utils.classes import Singleton
from utils.functions import find_paths_to_all_files_of_type
from utils.game_logging import log

from arcade import load_sound, play_sound, stop_sound, Sound
from pyglet.media import Player


SOUNDS_DIRECTORY = 'resources/sounds'
SOUNDS_EXTENSION = 'wav'
MUSIC_TRACK_SUFFIX = 'theme'
UNITS_MOVE_ORDERS_CONFIRMATIONS = [f'on_unit_get_order_{i}.wav' for i in range(6)]
UNITS_SELECTION_CONFIRMATIONS = [f'on_unit_selected_{i}.wav' for i in range(6)]
UNIT_PRODUCTION_FINISHED = [f'unit_{end}.wav' for end in ("ready", "complete")]


class AudioPlayer(Singleton):
    instance = None

    def __init__(self,
                 sounds_directory: str = SOUNDS_DIRECTORY,
                 sound_on: bool = True,
                 music_on: bool = True,
                 sound_effects_on: bool = True):
        """
        AudioPlayer is a singleton.

        :param sounds_directory: str -- name of the directory without path
        :param sound_on: bool -- if sounds should be played or not
        """
        self._music_on = music_on
        self._sound_effects_on = sound_effects_on

        self.volume: float = 0.5
        self.music_volume = self.volume
        self.effects_volume = self.volume

        self.sounds: Dict[str, Sound] = self._preload_sounds(sounds_directory)
        self.currently_played: List[Player] = []
        self.current_music: Optional[Player] = None
        log(f'Loaded {len(self.sounds)} sounds.', console=True)

        self.paused_track_name: Optional[str] = None
        self.paused_track_time: Optional[float] = None

        self.playlists: Dict[str, List[str]] = self._setup_playlists()
        self.current_playlist: Optional[List[str]] = None
        self.playlist_index: int = 0

        AudioPlayer.instance = self

        log(f'Found {len(self.playlists)} playlists', console=True)

    @staticmethod
    def _preload_sounds(sounds_directory=None) -> Dict[str, Sound]:
        names_to_paths = find_paths_to_all_files_of_type(SOUNDS_EXTENSION,
                                                         sounds_directory)
        return {
            name: load_sound(f'{path}/{name}', streaming=False) for
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
    def music_on(self) -> bool:
        return self._music_on

    @music_on.setter
    def music_on(self, value: bool):
        self._music_on = value
        if value and self.paused_track_name is not None:
            self._play_paused_music_track()
        else:
            self._pause_current_music_track()

    def _play_paused_music_track(self):
        self.play_music(self.paused_track_name, False)
        self.current_music.seek(self.paused_track_time)

    def _pause_current_music_track(self):
        self.paused_track_time = self.current_music.time
        self.paused_track_name = self._current_track_name()
        self.current_music.pause()

    def _current_track_name(self) -> str:
        return self.current_playlist[self.playlist_index]

    @property
    def sound_effects_on(self):
        return self._sound_effects_on

    @sound_effects_on.setter
    def sound_effects_on(self, value: bool):
        self._sound_effects_on = value

    def on_update(self):
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

    def play_sound(self, name: str, volume: Optional[float] = None):
        """Play a single sound. Use this for sound effects."""
        if name not in self.sounds:
            log(f'Sound: {name} not found!', console=True)
        elif self.is_music(name) and not self._music_on:
            pass
        elif not self._sound_effects_on:
            pass
        else:
            self._play_sound(name, loop=False, volume=volume)

    def play_music(self, name: str, loop=True, volume: Optional[float] = None):
        """Use this for background sound-themes."""
        if self.current_music is not None:
            self._stop_music_track()
        if self._music_on:
            self._play_music_track(name, loop, volume)

    def play_random(self, sounds_list: List[str], volume: Optional[float] = None):
        """Play sound randomly chosen from list of sounds names."""
        self.play_sound(random.choice(sounds_list), volume)

    def _stop_music_track(self):
        try:
            stop_sound(self.current_music)
        except AttributeError:
            pass
        finally:
            self.current_music = None

    def _play_music_track(self, name, loop, volume):
        player = self._get_player(name, loop, volume or self.music_volume)
        self.current_music = player

    def _play_sound(self, name, loop, volume):
        player = self._get_player(name, loop, volume or self.effects_volume)
        self.currently_played.append(player)

    def _get_player(self, name, loop, volume) -> Player:
        volume = min(volume, self.volume)
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
