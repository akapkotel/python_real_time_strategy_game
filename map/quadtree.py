#!/usr/bin/env python
from __future__ import annotations

from math import dist

from arcade import draw_rectangle_outline, draw_text

from utils.colors import RED


class Rect:
    __slots__ = ('cx', 'cy', 'position', 'width', 'height', 'smaller_dimension', 'left', 'right', 'bottom', 'top')

    def __init__(self, cx, cy, width, height):
        self.cx, self.cy = cx, cy
        self.position = self.cx, self.cy
        self.width, self.height = width, height
        self.smaller_dimension = min(self.width, self.height) / 2
        self.left = self.cx - self.width // 2
        self.right = self.left + self.width
        self.bottom = self.cy - self.height // 2
        self.top = self.bottom + self.height

    def in_bounds(self, item) -> bool:
        return (
                self.left <= item.position[0] <= self.right and self.bottom <= item.position[1] <= self.top
        )

    def intersects(self, other):
        return not ((other.right < self.left or self.right < other.left) and
                    (other.top < self.bottom or self.top < other.bottom))


class QuadTree(Rect):
    __slots__ = ('max_entities', 'true_max_entitites','depth', 'entities_count', 'entities', 'children', 'max_size')

    def __init__(self, cx, cy, width, height, max_entities=5, depth=0):
        super().__init__(cx, cy, width, height)
        self.max_entities = max_entities
        self.depth = depth
        self.entities_count = 0
        self.entities = {}
        self.children = []

    def __repr__(self) -> str:
        return f'QuadTree(depth: {self.depth}, position:{self.position})'

    def insert(self, entity):
        if not self.in_bounds(entity):
            return None

        if self.entities_count < self.max_entities:
            self.add_to_entities(entity)
            self.entities_count += 1
            return self

        if not self.children:
            self.divide()

        for quadtree in self.children:
            if quadtree.insert(entity) is not None:
                return quadtree
        print('FAILURE!')

    def add_to_entities(self, entity):
        index = entity.faction.id
        try:
            self.entities[index].add(entity)
        except KeyError:
            self.entities[index] = {entity,}

    def remove(self, entity):
        try:
            self.entities[entity.faction.id].remove(entity)
            self.entities_count -= 1
            print(f'Removed {entity} from {self}')
            self.collapse()
        except (KeyError, ValueError):
            for quadtree in self.children:
                    quadtree.remove(entity)

    def divide(self):
        cx, cy = self.cx, self.cy
        half_w, half_h = self.width / 2, self.height / 2
        quart_w, quart_h = half_w / 2, half_h / 2
        new_depth = self.depth + 1
        self.children = [
            QuadTree(cx - quart_w, cy - quart_h, half_w, half_h, self.max_entities, new_depth),
            QuadTree(cx + quart_w, cy - quart_h, half_w, half_h, self.max_entities, new_depth),
            QuadTree(cx + quart_w, cy + quart_h, half_w, half_h, self.max_entities, new_depth),
            QuadTree(cx - quart_w, cy + quart_h, half_w, half_h, self.max_entities, new_depth)
        ]

    def query(self, hostile_factions_ids, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""

        if not self.intersects(bounds):
            # If the domain of this node does not intersect the search
            # region, we don't need to look in it for points.
            return found_entities

        # Search this node's points to see if they lie within boundary ...
        for id, entities in self.entities.items():
            if id in hostile_factions_ids:
                found_entities.extend(e for e in entities if bounds.in_bounds(e))

        for quadtree in self.children:
            found_entities = quadtree.query(hostile_factions_ids, bounds, found_entities)
        return found_entities

    def find_selectable_units(self, left, right, bottom, top, faction_id):
        rect = Rect(left + right // 2, bottom + top // 2, right - left, top - bottom)
        possible_units = []
        return self.query(faction_id, rect, possible_units)

    def find_visible_entities_in_circle(self, circle_x, circle_y, radius, hostile_factions_ids):
        diameter = radius + radius
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(hostile_factions_ids, rect, possible_enemies)
        return {e for e in possible_enemies if dist(e.position, (circle_x, circle_y)) < radius}

    @property
    def empty(self):
        return not self.entities and all(child.empty() for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return self.entities_count == 0 and self.children

    def clear(self):
        for quadtree in self.children:
            quadtree.clear()
        self.entities.clear()

    def total_depth(self, depth=0) -> int:
        for quadtree in self.children:
            depth = quadtree.total_depth(depth)
        return max(depth, self.depth)

    def total_entities(self, count=0):
        for quadtree in self.children:
            count += quadtree.total_entities()
        return self.entities_count + count

    def get_entities(self):
        entitites = []
        for e in self.entities.values():
            entitites.extend(e)
        return [e.id for e in entitites]

    def draw(self):
        draw_rectangle_outline(*self.position, self.width, self.height, RED)
        draw_text(str(self.get_entities()), *self.position, RED, 20)
        for child in self.children:
            child.draw()
