#!/usr/bin/env python
from __future__ import annotations

from typing import Tuple, Union, List, Literal


from utils.data_types import GridPosition

# explosions
EXPLOSION_SMALL_5 = 'EXPLOSION_SMALL_5'
HIT_BLAST = 'HIT_BLAST'
SHOT_BLAST = 'SHOT_BLAST'
EXPLOSION = "EXPLOSION"

# cursor
CURSOR_NORMAL_TEXTURE = 0
CURSOR_FORBIDDEN_TEXTURE = 1
CURSOR_ATTACK_TEXTURE = 2
CURSOR_SELECTION_TEXTURE = 3
CURSOR_MOVE_TEXTURE = 4
CURSOR_REPAIR_TEXTURE = 6
CURSOR_ENTER_TEXTURE = 5
HORIZONTAL = 'diagonal'
VERTICAL = 'vertical'

# gameobjects
CLASS = 'class'
TREE = 'tree'
CORPSE = 'corpse'
WRECK = 'wreck'
UNITS = 'units'
BUILDINGS = 'buildings'
UNIT = 'Unit'
VEHICLE_WITH_TURRET = 'VehicleWithTurret'
VEHICLE = 'Vehicle'
SOLDIER = 'Soldier'
BUILDING = 'Building'
CONSTRUCTION_SITE = 'construction_site'
RESEARCH_FACILITY = 'research_facility'
PRODUCED_RESOURCE = 'produced_resource'
PRODUCED_UNITS = 'produced_units'

# map
TILE_WIDTH = 60
TILE_HEIGHT = 50
PATH = 'PATH'
VERTICAL_DIST = 10
DIAGONAL_DIST = 14  # approx square root of 2
ADJACENT_OFFSETS = [
    (-1, -1), (-1, 0), (-1, +1), (0, +1), (0, -1), (+1, -1), (+1, 0), (+1, +1)
]
OPTIMAL_PATH_LENGTH = 50
NormalizedPoint = Tuple[int, int]
MapPath = Union[List[NormalizedPoint], List[GridPosition]]
PathRequest = Tuple['Unit', GridPosition, GridPosition]
TreeID = int

# factions and players
REPUBLIC = 'Solarian Republic'
CONGLOMERATE = 'Interplanetary Industrial Conglomerate'
COLONISTS = 'Colonists'
FUEL = 'fuel'
FOOD = 'food'
AMMUNITION = 'ammunition'
ENERGY = 'energy'
STEEL = 'steel'
ELECTRONICS = 'electronics'
CONSCRIPTS = 'conscripts'
YIELD_PER_SECOND = "_yield_per_second"
CONSUMPTION_PER_SECOND = "_consumption_per_second"
PRODUCTION_EFFICIENCY = "_production_efficiency"
FactionName = Literal['Solarian Republic', 'Interplanetary Industrial Conglomerate', 'Colonists', None]
RESOURCES = (FUEL, ENERGY, AMMUNITION, STEEL, ELECTRONICS, FOOD, CONSCRIPTS)

# user interface
EDITOR = 'editor'
SCENARIOS = 'scenarios'
PROJECTS = 'projects'
SAVED_GAMES = 'saves'
SCENARIO_EDITOR_MENU = 'scenario editor menu'
MULTIPLAYER_MENU = 'multiplayer menu'
NEW_GAME_MENU = 'new game menu'
SKIRMISH_MENU = 'skirmish menu'
CAMPAIGN_MENU = 'campaign menu'
LOADING_MENU = 'loading menu'
SAVING_MENU = 'saving menu'
MAIN_MENU = 'main menu'
OPTIONS_SUBMENU = 'options'
GRAPHICS_TAB = 'graphics tab'
SOUND_TAB = 'sound tab'
GAME_TAB = 'game tab'
CREDITS_SUBMENU = 'credits'
CONFIRMATION_DIALOG = 'Confirmation dialog'
NOT_AVAILABLE_NOTIFICATION = 'Not available yet...'
PADDING_X = 5
PADDING_Y = 30
MINIMAP_WIDTH = 388
MINIMAP_HEIGHT = 197
UI_OPTIONS_PANEL = 'ui_options_panel'
UI_RESOURCES_SECTION = 'ui_resources_section'
UI_BUILDINGS_PANEL = 'ui_building_panel'
UI_UNITS_PANEL = 'ui_units_panel'
UI_UNITS_CONSTRUCTION_PANEL = 'ui_units_construction_panel'
UI_BUILDINGS_CONSTRUCTION_PANEL = 'ui_buildings_construction_panel'
UI_TERRAIN_EDITING_PANEL = 'ui_terrain_editing_panel'
QUIT_GAME_BUTTON = 'quit game button'
CONTINUE_BUTTON = 'continue button'
SAVE_GAME_BUTTON = 'save game button'
