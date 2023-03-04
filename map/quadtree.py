#!/usr/bin/env python
from __future__ import annotations

from math import dist
from typing import Optional

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
        return f'QuadTree(depth: {self.depth}, l:{self.left}, r:{self.right}, b:{self.bottom}, t:{self.top})'

    def insert(self, entity) -> Optional[QuadTree]:
        if not self.in_bounds(entity):
            return None

        if self.entities_count < self.max_entities:
            self.add_to_entities(entity)
            return self

        if not self.children:
            self.divide()

        return self.insert_to_children(entity)

    def insert_to_children(self, entity) -> Optional[QuadTree]:
        for child in self.children:
            if (quadtree := child.insert(entity)) is not None:
                return quadtree

    def add_to_entities(self, entity):
        faction_id = entity.faction.id
        try:
            self.entities[faction_id].add(entity)
        except KeyError:
            self.entities[faction_id] = {entity,}
        finally:
            self.entities_count += 1

    def remove(self, entity):
        try:
            self.entities[entity.faction.id].remove(entity)
        except (KeyError, ValueError):
            for quadtree in self.children:
                    quadtree.remove(entity)
        else:
            self.entities_count -= 1
            self.collapse()

    def divide(self):
        cx, cy = self.cx, self.cy
        half_width, half_height = self.width / 2, self.height / 2
        quart_width, quart_height = half_width / 2, half_height / 2
        new_depth = self.depth + 1
        self.children = [
            QuadTree(cx - quart_width, cy + quart_height, half_width, half_height, self.max_entities, new_depth),
            QuadTree(cx + quart_width, cy + quart_height, half_width, half_height, self.max_entities, new_depth),
            QuadTree(cx + quart_width, cy - quart_height, half_width, half_height, self.max_entities, new_depth),
            QuadTree(cx - quart_width, cy - quart_height, half_width, half_height, self.max_entities, new_depth)
        ]

    def query(self, hostile_factions_ids, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""

        if not self.intersects(bounds):
            # If the domain of this node does not intersect the search
            # region, we don't need to look in it for points.
            return found_entities

        # Search this node's points to see if they lie within boundary ...
        for faction_id, entities in self.entities.items():
            if faction_id in hostile_factions_ids:
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
        return not (self.children or self.entities_count)

    def clear(self):
        for quadtree in self.children:
            quadtree.clear()
        self.entities.clear()

    def total_depth(self, depth=0) -> int:
        for quadtree in self.children:
            depth = quadtree.total_depth(depth)
        return max(depth, self.depth)

    def total_entities(self):
        return self.entities_count + sum(quadtree.total_entities() for quadtree in self.children)

    def get_entities(self):
        # for entities_list in self.entities.values():
        #     for e in entities_list:
        return [e.id for entities_list in self.entities.values() for e in entities_list]


    def draw(self):
        draw_rectangle_outline(*self.position, self.width, self.height, RED)
        draw_text(str(self.get_entities()), *self.position, RED, 20)
        for child in self.children:
            child.draw()