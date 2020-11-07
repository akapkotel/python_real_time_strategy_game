#!/usr/bin/env python

from typing import Tuple, Set, Sequence, Optional

from arcade import load_texture, Sprite, SpriteSolidColor
from arcade.arcade_types import Color, Point

from utils.functions import get_path_to_file, average_position_of_points_group
from colors import GREEN, YELLOW, RED
from player import PlayerEntity
from units import Unit
from game import Game

selection_texture = load_texture(
    get_path_to_file('unit_selection_marker.png'), 0, 0, 60, 60
)


class SelectedEntityMarker:
    """
    This class produces rectangle-unit-selection markers showing that a
    particular Unit or Building is selected by player and displaying some
    info about selected, like health level or lack of fuel icon. Each marker
    can contain many Sprites which are dynamically created, updated and
    destroyed. You must cache SelectionMarker instances and their Sprites in
    distinct data-structures. Markers are stored in ordinary list and
    Sprites in SpriteLists.
    """

    def __init__(self, selected: PlayerEntity):
        self.selected = selected
        selected.selection_marker = self
        self.health = health = selected.health
        self.position = selected.position
        self.borders = borders = Sprite()
        borders.texture = selection_texture
        self.healthbar = healthbar = SpriteSolidColor(
            *self.health_to_color_and_width(health))
        self.sprites = [borders, healthbar]

    @staticmethod
    def health_to_color_and_width(health: float) -> Tuple[float, int, Color]:
        width = int((60 / 100) * health)
        if health > 66:
            return width, 5, GREEN
        return (width, 5, YELLOW) if health > 33 else (width, 5, RED)

    def update(self):
        self.position = x, y = self.selected.position
        self.update_healthbar(x, y)
        for sprite in self.sprites[:-1]:
            sprite.position = x, y

    def update_healthbar(self, x, y):
        if (health := self.selected.health) != self.health:
            width, _, color = self.health_to_color_and_width(health)
            self.healthbar.color = color
            self.healthbar.width = width
        self.healthbar.position = x - (100 - health) * 0.3, y + 30

    def kill(self):
        for sprite in self.sprites:
            sprite.kill()


class PermanentUnitsGroup:
    """
    Player can group units by selecting them with mouse and pressing CTRL +
    numeric keys (1-9). Such groups could be then quickly selected by pressing
    their numbers.
    """
    game: Optional[Game] = None

    def __init__(self, group_id: int, units: Sequence[Unit]):
        self.group_id = group_id
        self.units: Set[Unit] = set(units)

    @property
    def position(self) -> Point:
        positions = [(u.center_x, u.center_y) for u in self.units]
        return average_position_of_points_group(positions)

    def discard(self, unit: Unit):
        self.units.discard(unit)
