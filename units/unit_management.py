#!/usr/bin/env python
from __future__ import annotations

from typing import Optional, Sequence, Set, Tuple, Iterator

from arcade import Sprite, SpriteSolidColor, load_texture
from arcade.arcade_types import Color, Point

from utils.colors import GREEN, RED, YELLOW
from game import Game
from players_and_factions.player import PlayerEntity
from units.units import Unit
from utils.functions import average_position_of_points_group, get_path_to_file

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
    game: Optional[Game] = None

    def __init__(self, selected: PlayerEntity):
        self.selected = selected
        selected.selection_marker = self
        self.health = health = selected.health
        self.position = selected.position
        self.borders = borders = Sprite()
        borders.texture = selection_texture
        self.healthbar = healthbar = SpriteSolidColor(
            *self.health_to_color_and_width(health))
        self.sprites = sprites = [borders, healthbar]
        self.game.selection_markers_sprites.extend(sprites)

    @staticmethod
    def health_to_color_and_width(health: float) -> Tuple[int, int, Color]:
        width = int((60 / 100) * health)
        if health > 66:
            return width, 5, GREEN
        return (width, 5, YELLOW) if health > 33 else (width, 5, RED)

    def update(self):
        if self.selected.alive:
            self.position = x, y = self.selected.position
            self.update_healthbar(x, y)
            for sprite in self.sprites[:-1]:
                sprite.position = x, y
        else:
            self.kill()

    def update_healthbar(self, x, y):
        if (health := self.selected.health) != self.health:
            width, height, color = self.health_to_color_and_width(health)
            if color != self.healthbar.color:
                self.replace_healthbar_with_new_color(color, height, width)
            else:
                self.healthbar.width = width
        self.healthbar.position = x - (100 - health) * 0.3, y + 30

    def replace_healthbar_with_new_color(self, color, height, width):
        self.healthbar.kill()
        self.healthbar = bar = SpriteSolidColor(width, height, color)
        self.sprites.append(self.healthbar)
        self.game.selection_markers_sprites.append(bar)

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
        self.game.permanent_units_groups[group_id] = self

    def __contains__(self, unit: Unit) -> bool:
        return unit in self.units

    def __iter__(self) -> Iterator:
        return iter(self.units)

    @property
    def position(self) -> Point:
        positions = [(u.center_x, u.center_y) for u in self.units]
        return average_position_of_points_group(positions)

    def discard(self, unit: Unit):
        self.units.discard(unit)

    @classmethod
    def create_new_permanent_units_group(cls, digit: int):
        units = PermanentUnitsGroup.game.window.cursor.selected_units
        new_group = PermanentUnitsGroup(group_id=digit, units=units)
        PermanentUnitsGroup.game.permanent_units_groups[digit] = new_group

    @classmethod
    def select_permanent_units_group(cls, group_id: int):
        try:
            game = PermanentUnitsGroup.game
            group = game.permanent_units_groups[group_id]
            selected = game.window.cursor.selected_units
            if selected and all(u in group for u in selected):
                game.window.move_viewport_to_the_position(*group.position)
            else:
                game.window.cursor.unselect_units()
                game.window.cursor.select_units(*group.units)
        except KeyError:
            pass
