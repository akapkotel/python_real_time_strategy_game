from __future__ import annotations

from enum import Enum
from typing import Literal

from utils.colors import GREEN, RED, BLUE, YELLOW

REPUBLIC = 'Solarian Republic'
CONGLOMERATE = 'Interplanetary Industrial Conglomerate'
COLONISTS = 'Colonists'
FactionName = Literal['Solarian Republic', 'Interplanetary Industrial Conglomerate', 'Colonists', None]
FUEL = 'fuel'
FOOD = 'food'
AMMUNITION = 'ammunition'
ENERGY = 'energy'
STEEL = 'steel'
ELECTRONICS = 'electronics'
CONSCRIPTS = 'conscripts'
RESOURCES = (FUEL, ENERGY, AMMUNITION, STEEL, ELECTRONICS, FOOD, CONSCRIPTS)
YIELD_PER_SECOND = "_yield_per_second"
CONSUMPTION_PER_SECOND = "_consumption_per_second"
PRODUCTION_EFFICIENCY = "_production_efficiency"


class PlayerColor(Enum):
    green = GREEN
    red = RED
    blue = BLUE
    yellow = YELLOW
