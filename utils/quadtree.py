#!/usr/bin/env python
from __future__ import annotations

import random
from typing import Tuple, Union
from dataclasses import dataclass


@dataclass
class Rect:
    cx: Union[int, float]
    cy: Union[int, float]
    width: Union[int, float]
    height: Union[int, float]

    def __post_init__(self):
        self.left = self.cx - self.width // 2
        self.right = self.left + self.width
        self.bottom = self.cy - self.height // 2
        self.top = self.bottom + self.height

    def in_bounds(self, item) -> bool:
        return (
            self.left <= item.position[0] <= self.right and self.bottom <= item.position[1] <= self.top
        )

    def intersects(self, other):
        return not (other.left > self.left or
                    other.right < self.right or
                    other.top > self.top or
                    other.bottom < self.bottom)


@dataclass
class QuadTree(Rect):
    max_entities: int = 10
    depth: int = 0
    divided = False

    def __post_init__(self):
        super().__post_init__()
        self.entities = []
        self.children = []

    def insert(self, entity) -> bool:

        if not self.in_bounds(entity):
            return False

        if len(self.entities) < self.max_entities:
            return self.add_to_entities(entity)

        if not self.divided:
            self.divide()

        for quadtree in self.children:
            if quadtree.insert(entity):
                return True

    def add_to_entities(self, entity) -> bool:
        self.entities.append(entity)
        try:
            entity.quadtree = self
        except AttributeError:
            setattr(entity, 'quadtree', self)
        return True

    def remove(self, entity):
        self.entities.remove(entity)

    def divide(self):
        cx, cy = self.cx, self.cy
        half_w, half_h = self.width / 2, self.height / 2
        quart_w, quart_h = half_w / 2, half_h / 2
        new_depth = self.depth + 1
        # The boundaries of the four children nodes are "northwest",
        # "northeast", "southeast" and "southwest" quadrants within the
        # boundary of the current node.
        self.children = [
            QuadTree(cx - quart_w, cy - quart_h, half_w, half_h, self.max_entities, new_depth),
            QuadTree(cx + quart_w, cy - quart_h, half_w, half_h, self.max_entities, new_depth),
            QuadTree(cx + quart_w, cy + quart_h, half_w, half_h, self.max_entities, new_depth),
            QuadTree(cx - quart_w, cy + quart_h, half_w, half_h, self.max_entities, new_depth)
        ]
        self.divided = True

    def query(self, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""

        if not self.intersects(bounds):
            # If the domain of this node does not intersect the search
            # region, we don't need to look in it for points.
            return found_entities

        # Search this node's points to see if they lie within boundary ...
        for entity in self.entities:
            if bounds.contains(entity):
                found_entities.append(entity)
        for quadtree in self.children:
            quadtree.query(bounds, found_entities)
        return found_entities

    @property
    def empty(self):
        return not self.entities and all(child.empty() for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return not (self.children or self.entities)

    def clear(self):
        if self.divided:
            for quadtree in self.children:
                quadtree.clear()
        self.entities.clear()

    def __len__(self, count=0) -> int:
        if self.divided:
            for quadtree in self.children:
                count += len(quadtree)
        return len(self.entities) + count


@dataclass
class Entity:
    position: Tuple[int, int]

    def __post_init__(self):
        self.quadtree = None

    def leave_quadtree(self):
        self.quadtree.remove(self)
        self.quadtree = None


if __name__ == '__main__':
    import time

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
