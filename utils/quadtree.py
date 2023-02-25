#!/usr/bin/env python
from __future__ import annotations

from math import dist


class Rect:
    __slots__ = ('cx', 'cy', 'position', 'width', 'height', 'smaller_dimension', 'left', 'right', 'bottom', 'top')

    def __init__(self, cx, cy, width, height):
        self.cx, self.cy = cx, cy
        self.position = self.cx, self.cy
        self.width, self.height = width, height
        self.smaller_dimension = min(self.width, self.height)
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
    __slots__ = ('max_entities', 'depth', 'entities', 'children')

    def __init__(self, cx, cy, width, height, max_entities=10, depth=0):
        super().__init__(cx, cy, width, height)
        self.max_entities = max_entities
        self.depth = depth
        self.entities = {}
        self.children = []

    def insert(self, entity):
        if not self.in_bounds(entity):
            return None

        if len(self.entities) < self.max_entities:
            self.add_to_entities(entity)
            # print(f'Inserted {entity} to {self}')
            return self

        if not self.children:
            self.divide()

        for quadtree in self.children:
            if quadtree.insert(entity) is not None:
                return quadtree

    def add_to_entities(self, entity):
        index = entity.faction.id
        try:
            self.entities[index].add(entity)
        except KeyError:
            self.entities[index] = {entity,}

    def remove(self, entity):
        try:
            self.entities[entity.faction.id].discard(entity)
        except (KeyError, ValueError):
            for quadtree in self.children:
                quadtree.remove(entity)
        else:
            self.collapse()
            # print(f'Removed {entity} from {self}')

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

    def query(self, entity_faction_id, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""

        if not self.intersects(bounds):
            # If the domain of this node does not intersect the search
            # region, we don't need to look in it for points.
            return found_entities

        # Search this node's points to see if they lie within boundary ...
        for id, entities in self.entities.items():
            if id != entity_faction_id:
                found_entities.extend(e for e in entities if bounds.in_bounds(e))

        for quadtree in self.children:
            found_entities = quadtree.query(entity_faction_id, bounds, found_entities)
        return found_entities

    def find_selectable_units(self, left, right, bottom, top, faction_id):
        rect = Rect(left + right // 2, bottom + top // 2, right - left, top - bottom)
        possible_units = []
        return self.query(faction_id, rect, possible_units)

    def find_visible_entities_in_circle(self, circle_x, circle_y, radius, entity_faction_id):
        diameter = radius + radius
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(entity_faction_id, rect, possible_enemies)
        return {e for e in possible_enemies if dist(e.position, (circle_x, circle_y)) < radius}

    @property
    def empty(self):
        return not any(self.entities.values()) and all(child.empty() for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return not (self.children or any(self.entities.values()))

    def clear(self):
        for quadtree in self.children:
            quadtree.clear()
        self.entities.clear()

    def __len__(self, count=0) -> int:
        for quadtree in self.children:
            count += len(quadtree)
        return len(self.entities) + count

    def total_depth(self, depth=0) -> int:
        for quadtree in self.children:
            depth = quadtree.total_depth(depth)
        return max(depth, self.depth)

    def total_entities(self, count=0):
        for quadtree in self.children:
            count += quadtree.total_entities()
        return sum(sum(e) for e in self.entities.values()) + count
