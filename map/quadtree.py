#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod, ABC
from math import dist
from typing import Optional, Set

import shapely.geometry
from matplotlib import path as mpltPath
from numpy import array

from arcade import draw_rectangle_outline, draw_text, draw_polygon_outline

from utils.colors import RED, WHITE
from utils.debugging import DebugInfo


class Rect:
    __slots__ = ('cx', 'cy', 'position', 'width', 'height', 'smaller_dimension', 'left', 'right', 'bottom', 'top', 'points')

    def __init__(self, cx, cy, width, height):
        self.cx, self.cy = cx, cy
        self.position = self.cx, self.cy
        self.width, self.height = width, height
        self.smaller_dimension = min(self.width, self.height) / 2
        self.left = self.cx - self.width // 2
        self.right = self.left + self.width
        self.bottom = self.cy - self.height // 2
        self.top = self.bottom + self.height
        self.points = [(self.left, self.top), (self.right, self.top), (self.left, self.bottom), (self.right, self.bottom)]

    def in_bounds(self, item) -> bool:
        return (
                self.left <= item.position[0] <= self.right and self.bottom <= item.position[1] <= self.top
        )

    def intersects_with(self, other):
        return not ((other.right < self.left or self.right < other.left) and
                    (other.top < self.bottom or self.top < other.bottom))

    def draw(self):
        draw_rectangle_outline(self.cx // 55, self.cy // 55, self.width // 10, self.height // 10, RED)


class IsometricRect(Rect):

    def __init__(self, cx, cy, width, height, w_ratio: float, h_ratio: float):
        super().__init__(cx, cy, width, height)
        self.w_ratio = w_ratio
        self.h_ratio = h_ratio

        hh, hw = height / 4, width / 2
        self.points = [(cx - hw, cy), (cx, cy + hh), (cx + hw, cy), (cx, cy - hh), (cx - hw, cy)]
        self.polygon = shapely.geometry.Polygon(self.points)
        l, b, r, t = self.polygon.bounds
        self.bbox_height = height = t - b
        self.bbox_width = width = r - l

        self.points = [
            (l, b + (height * w_ratio)), (r - (width * w_ratio), cy + hh), (r, t - (height * w_ratio)),
            (l + (width * w_ratio), b), (l, b + (height * w_ratio))
        ]
        self.polygon = mpltPath.Path(array(self.points))

    def in_bounds(self, item) -> bool:
        return self.polygon.contains_point(item.position)

    def intersects_with(self, other) -> bool:
        """
        Check if the polygon intersects with another polygon.

        Args:
            other: The other polygon to check for intersection.

        Returns:
            True if the polygons intersect, False otherwise.
        """
        return any(self.polygon.contains_point(point) for point in other.points)

    def draw(self):
        draw_polygon_outline(self.points, RED, 1)


class QuadTree(ABC):
    count = 0

    def __init__(self, max_entities=5, depth=0):
        self.id = QuadTree.count
        QuadTree.count += 1
        self.max_entities = max_entities
        self.entities_count = 0
        self.depth = depth
        self.entities = {}
        self.children = []

    @abstractmethod
    def query(self, hostile_factions_ids, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""
        raise NotImplementedError

    def find_visible_entities_in_circle(self, circle_x, circle_y, radius, hostile_factions_ids):
        diameter = radius * 2
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(hostile_factions_ids, rect, possible_enemies)
        return {e for e in possible_enemies if dist(e.position, (circle_x, circle_y)) < radius}

    @abstractmethod
    def insert(self, entity) -> Optional[QuadTree]:
        raise NotImplementedError

    def insert_to_children(self, entity) -> Optional[CartesianQuadTree]:
        for child in self.children:
            if (quadtree := child.insert(entity)) is not None:
                return quadtree

    def add_to_entities(self, entity):
        faction_id = entity.faction.id
        try:
            self.entities[faction_id].add(entity)
        except KeyError:
            self.entities[faction_id] = {entity, }
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

    @abstractmethod
    def divide(self):
        raise NotImplementedError

    @property
    def empty(self):
        return not self.entities and all(child.empty() for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return not self.children and not self.entities_count

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

    @property
    def get_entities(self):
        return [e.id for entities_list in self.entities.values() for e in entities_list]


class CartesianQuadTree(QuadTree, Rect):
    """This class provides fast and efficient way to detect Units which could see each other."""
    __slots__ = ('max_entities', 'true_max_entities','depth', 'entities_count', 'entities', 'children', 'max_size')

    def __init__(self, cx, cy, width, height, max_entities=5, depth=0):
        super().__init__(max_entities, depth)
        Rect.__init__(self, cx, cy, width, height)

    def __repr__(self) -> str:
        return f'QuadTree(depth: {self.depth}, l:{self.left}, r:{self.right}, b:{self.bottom}, t:{self.top})'

    def insert(self, entity) -> Optional[CartesianQuadTree]:
        if not Rect.in_bounds(self, entity):
            return None

        if self.entities_count < self.max_entities:
            self.add_to_entities(entity)
            return self

        if not self.children:
            self.divide()

        return self.insert_to_children(entity)

    def insert_to_children(self, entity) -> Optional[CartesianQuadTree]:
        for child in self.children:
            if (quadtree := child.insert(entity)) is not None:
                return quadtree

    def add_to_entities(self, entity):
        faction_id = entity.faction.id
        try:
            self.entities[faction_id].add(entity)
        except KeyError:
            self.entities[faction_id] = {entity, }
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
            CartesianQuadTree(cx - quart_width, cy + quart_height, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx + quart_width, cy + quart_height, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx + quart_width, cy - quart_height, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx - quart_width, cy - quart_height, half_width, half_height, self.max_entities, new_depth)
        ]

    def query(self, hostile_factions_ids, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""
        if not self.intersects_with(bounds):
            return found_entities
        for faction_id, entities in self.entities.items():
            if faction_id in hostile_factions_ids:
                found_entities.extend(e for e in entities if bounds.in_bounds(e))
        for quadtree in self.children:
            found_entities = quadtree.query(hostile_factions_ids, bounds, found_entities)
        return found_entities

    def find_visible_entities_in_circle(self, circle_x, circle_y, radius, hostile_factions_ids):
        diameter = radius + radius
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(hostile_factions_ids, rect, possible_enemies)
        return {e for e in possible_enemies if dist(e.position, (circle_x, circle_y)) < radius}

    @property
    def empty(self):
        return not self.entities and all(child.empty for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return not self.children and not self.entities_count

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

    @property
    def get_entities(self):
        return [e.id for entities_list in self.entities.values() for e in entities_list]

    def draw(self):
        super().draw()
        if self.entities_count:
            draw_text(str(self.get_entities()), *self.position, RED, 20)
        for child in self.children:
            child.draw()


class IsometricQuadTree(QuadTree, IsometricRect):

    def __init__(self, cx, cy, width, height, w_ratio, h_ratio, max_entities=5, depth=0):
        super().__init__(max_entities, depth)
        IsometricRect.__init__(self, cx, cy, width, height, w_ratio, h_ratio)
        self.tiles: Set[int] = set()  # TODO: find efficient way to register Tiles to Quads for faster spatial checks
        self.debug_info = DebugInfo(f'{self.id}: {[e.id for e in self.get_entities]}', *self.position, RED, 20)

    def __repr__(self) -> str:
        return f'QuadTree(depth: {self.depth}, l:{self.left}, r:{self.right}, b:{self.bottom}, t:{self.top})'

    def insert(self, entity) -> Optional[IsometricQuadTree]:
        if not self.in_bounds(entity):
            return None

        if self.entities_count < self.max_entities:
            self.add_to_entities(entity)
            return self

        if not self.children:
            self.divide()

        return self.insert_to_children(entity)

    def insert_to_children(self, entity) -> Optional[IsometricQuadTree]:
        for child in self.children:
            if (quadtree := child.insert(entity)) is not None:
                return quadtree

    def add_to_entities(self, entity):
        faction_id = entity.faction.id
        try:
            self.entities[faction_id].add(entity)
        except KeyError:
            self.entities[faction_id] = {entity, }
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
        quart_width, quart_height = half_width / 2, half_height / 4
        new_depth = self.depth + 1
        max_entities = self.max_entities
        w_ratio, h_ratio, bbox_height, bbox_width = self.w_ratio, self.h_ratio, self.bbox_height, self.bbox_width

        if w_ratio > h_ratio:  # left-tilted quad (map has more columns than rows)
            self.children = [
                IsometricQuadTree(cx - quart_width, cy + bbox_height // 2 * h_ratio, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx - bbox_width // 2 * h_ratio, cy + quart_height, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx + quart_width, cy - bbox_height // 2 * h_ratio, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx + bbox_width // 2 * h_ratio, cy - quart_height, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth)
            ]
        elif h_ratio > w_ratio:  # right-tilted quad (more rows)
            self.children = [
                IsometricQuadTree(cx - quart_width, cy - bbox_height // 2 * w_ratio, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx + bbox_width // 2 * w_ratio, cy + quart_height, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx + quart_width, cy + bbox_height // 2 * w_ratio, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx - bbox_width // 2 * w_ratio, cy - quart_height, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth)
            ]
        else:  # square quad (rows == cols)
            self.children = [
                IsometricQuadTree(cx - quart_width, cy, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx, cy + quart_height, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx + quart_width, cy, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth),
                IsometricQuadTree(cx, cy - quart_height, half_width, half_height, w_ratio, h_ratio, max_entities, new_depth)
            ]

    def query(self, hostile_factions_ids, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""
        if not self.intersects_with(bounds):
            return found_entities
        in_bounds = bounds.in_bounds
        for faction_id, entities in self.entities.items():
            if faction_id in hostile_factions_ids:
                found_entities.extend(e for e in entities if in_bounds(e))
        for quadtree in self.children:
            found_entities = quadtree.query(hostile_factions_ids, bounds, found_entities)
        return found_entities

    def find_visible_entities_in_circle(self, circle_x, circle_y, radius, hostile_factions_ids):
        diameter = radius * 2
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(hostile_factions_ids, rect, possible_enemies)
        return {e for e in possible_enemies if dist(e.position, (circle_x, circle_y)) < radius}

    @property
    def empty(self):
        return not self.entities and all(child.empty for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return not self.children and not self.entities_count

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

    @property
    def get_entities(self):
        return [e for entities_list in self.entities.values() for e in entities_list]

    def update_debug(self):
        self.debug_info.update(f'{self.id}: {[e.id for e in self.get_entities]}', self.cx, self.cy)
        for child in self.children:
            child.update_debug()

    def draw(self):
        super().draw()
        self.debug_info.draw()
        for child in self.children:
            child.draw()
