from dataclasses import dataclass
from typing import Optional

from arcade import draw_text, Color


@dataclass
class DebugInfo:
    __slots__ = ('text', 'x', 'y', 'color', 'text_size')
    text: str
    x: float
    y: float
    color: Color
    text_size: int

    def update(self, text: str, x: float, y: float, color: Optional[Color] = None, text_size: Optional[int] = None):
        for k, v in locals().items():
            if k != 'self' and v is not None:
                setattr(self, k, v)

    def draw(self):
        draw_text(self.text, self.x, self.y, self.color, self.text_size, anchor_x='center', anchor_y='center')
