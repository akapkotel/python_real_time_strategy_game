#!/usr/bin/env python
from __future__ import annotations

from math import dist
from typing import Tuple, Union
from dataclasses import dataclass


@dataclass
class Rect:
    cx: Union[int, float]
    cy: Union[int, float]
    width: Union[int, float]
    height: Union[int, float]

    def __post_init__(self):
        self.position = self.cx, self.cy
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


@dataclass
class QuadTree(Rect):
    max_entities: int = 10
    depth: int = 0
    divided = False

    def __post_init__(self):
        super().__post_init__()
        self.entities = {}
        self.children = []

    def insert(self, entity):

        if not self.in_bounds(entity):
            return False

        if len(self.entities) < self.max_entities:
            self.add_to_entities(entity)
            # print(f'Inserted {entity} to {self}')
            return True

        if not self.children:
            self.divide()

        for quadtree in self.children:
            if quadtree.insert(entity):
                return True

    def add_to_entities(self, entity):
        index = entity.faction.id
        try:
            self.entities[index].add(entity)
        except KeyError:
            self.entities[index] = {entity,}
        try:
            entity.quadtree = self
        except AttributeError:
            setattr(entity, 'quadtree', self)

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

    def query(self, entity_id, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""

        if not self.intersects(bounds):
            # If the domain of this node does not intersect the search
            # region, we don't need to look in it for points.
            return found_entities

        # Search this node's points to see if they lie within boundary ...
        for id, entities in self.entities.items():
            found_entities.extend(e for e in entities if id != entity_id and bounds.in_bounds(e))

        for quadtree in self.children:
            quadtree.query(entity_id, bounds, found_entities)
        return found_entities

    def query_circle(self, circle_x, circle_y, radius, entity_id):
        diameter = radius + radius
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(entity_id, rect, possible_enemies)
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


if __name__ == '__main__':
    import time
    import random

    @dataclass
    class Entity:
        position: Tuple[int, int]

        def __post_init__(self):
            self.quadtree = None

        def leave_quadtree(self):
            self.quadtree.remove(self)
            self.quadtree = None


    entities = [Entity((random.randint(1, 600), random.randint(1, 600))) for _ in range(60)]
    tree = QuadTree(300, 300, 600, 600, max_entities=5)

    start = time.perf_counter()
    for _ in range(1):
        for entity in entities:
            tree.insert(entity)
        for entity in entities:
            if random.random() > 0.6:
                entity.leave_quadtree()
        tree.collapse()
    stop = time.perf_counter() - start
    print(stop)
