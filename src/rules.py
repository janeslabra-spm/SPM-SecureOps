from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from src.detector import Detection


PHONE_ON_TABLE = "PHONE_ON_TABLE"
PHONE_HELD_OR_NEAR_PERSON = "PHONE_HELD_OR_NEAR_PERSON"


@dataclass(frozen=True)
class IncidentCandidate:
    incident_type: str
    confidence: float
    phone_bbox: tuple[int, int, int, int]
    person_bbox: tuple[int, int, int, int] | None = None


def table_zone_from_percent(
    frame_width: int,
    frame_height: int,
    x1_percent: int,
    y1_percent: int,
    x2_percent: int,
    y2_percent: int,
) -> tuple[int, int, int, int]:
    x1 = int(frame_width * x1_percent / 100)
    y1 = int(frame_height * y1_percent / 100)
    x2 = int(frame_width * x2_percent / 100)
    y2 = int(frame_height * y2_percent / 100)
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def classify_incidents(
    detections: list[Detection],
    table_zone: tuple[int, int, int, int],
    proximity_pixels: int = 80,
) -> list[IncidentCandidate]:
    people = [detection for detection in detections if detection.label == "person"]
    phones = [detection for detection in detections if detection.label == "cell phone"]

    candidates: list[IncidentCandidate] = []
    for phone in phones:
        nearest_person = _nearest_person(phone.bbox, people, proximity_pixels)
        if nearest_person is not None:
            candidates.append(
                IncidentCandidate(
                    incident_type=PHONE_HELD_OR_NEAR_PERSON,
                    confidence=phone.confidence,
                    phone_bbox=phone.bbox,
                    person_bbox=nearest_person.bbox,
                )
            )
            continue

        if _center_inside(phone.bbox, table_zone):
            candidates.append(
                IncidentCandidate(
                    incident_type=PHONE_ON_TABLE,
                    confidence=phone.confidence,
                    phone_bbox=phone.bbox,
                )
            )

    return candidates


def _center_inside(
    bbox: tuple[int, int, int, int],
    zone: tuple[int, int, int, int],
) -> bool:
    x1, y1, x2, y2 = bbox
    zx1, zy1, zx2, zy2 = zone
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    return zx1 <= cx <= zx2 and zy1 <= cy <= zy2


def _nearest_person(
    phone_bbox: tuple[int, int, int, int],
    people: list[Detection],
    proximity_pixels: int,
) -> Detection | None:
    for person in people:
        if _boxes_overlap(phone_bbox, person.bbox):
            return person

    px, py = _bbox_center(phone_bbox)
    nearest: tuple[float, Detection] | None = None
    for person in people:
        distance = _distance_to_box(px, py, person.bbox)
        if distance <= proximity_pixels and (nearest is None or distance < nearest[0]):
            nearest = (distance, person)

    return nearest[1] if nearest else None


def _bbox_center(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


def _boxes_overlap(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return max(ax1, bx1) < min(ax2, bx2) and max(ay1, by1) < min(ay2, by2)


def _distance_to_box(x: float, y: float, bbox: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = bbox
    dx = max(x1 - x, 0, x - x2)
    dy = max(y1 - y, 0, y - y2)
    return hypot(dx, dy)
