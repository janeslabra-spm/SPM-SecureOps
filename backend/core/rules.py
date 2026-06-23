from __future__ import annotations

import logging
from dataclasses import dataclass
from math import hypot

from backend.core.detector import Detection


logger = logging.getLogger(__name__)

PHONE_ON_TABLE = "PHONE_ON_TABLE"
PHONE_NEAR_PERSON = "PHONE_NEAR_PERSON"
DOCUMENT_LEFT_ON_DESK = "DOCUMENT_LEFT_ON_DESK"


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
    """Convert percentage-based zone coordinates to pixel coordinates.

    Normalizes so that the returned tuple is (min_x, min_y, max_x, max_y).
    """
    x1 = int(frame_width * x1_percent / 100)
    y1 = int(frame_height * y1_percent / 100)
    x2 = int(frame_width * x2_percent / 100)
    y2 = int(frame_height * y2_percent / 100)
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def classify_incidents(
    detections: list[Detection],
    table_zone: tuple[int, int, int, int] | None,
    proximity_pixels: int = 80,
) -> list[IncidentCandidate]:
    """Classify detections into security violation incidents.

    Rules applied:
    - PHONE_NEAR_PERSON: cell phone overlaps or is within proximity_pixels of a person
    - PHONE_ON_TABLE: cell phone center is inside the desk zone (only if not near a person)
    - DOCUMENT_LEFT_ON_DESK: book/document center is inside the desk zone

    PHONE_NEAR_PERSON takes priority over PHONE_ON_TABLE for the same phone.

    If table_zone is None, zone-based classifications (PHONE_ON_TABLE and
    DOCUMENT_LEFT_ON_DESK) are skipped. A WARNING is logged for skipped
    document classifications indicating no Desk_Zone is defined.
    """
    people = [detection for detection in detections if detection.label == "person"]
    phones = [detection for detection in detections if detection.label == "cell phone"]
    documents = [detection for detection in detections if detection.label == "document"]

    candidates: list[IncidentCandidate] = []

    # Evaluate each phone independently
    for phone in phones:
        nearest_person = _nearest_person(phone.bbox, people, proximity_pixels)
        if nearest_person is not None:
            # PHONE_NEAR_PERSON has priority over PHONE_ON_TABLE
            candidates.append(
                IncidentCandidate(
                    incident_type=PHONE_NEAR_PERSON,
                    confidence=phone.confidence,
                    phone_bbox=phone.bbox,
                    person_bbox=nearest_person.bbox,
                )
            )
            continue

        if table_zone is not None and _center_inside(phone.bbox, table_zone):
            candidates.append(
                IncidentCandidate(
                    incident_type=PHONE_ON_TABLE,
                    confidence=phone.confidence,
                    phone_bbox=phone.bbox,
                )
            )

    # Evaluate each document/book independently
    if table_zone is None:
        if documents:
            logger.warning(
                "No Desk_Zone configured; skipping DOCUMENT_LEFT_ON_DESK classification"
            )
    else:
        for doc in documents:
            if _center_inside(doc.bbox, table_zone):
                candidates.append(
                    IncidentCandidate(
                        incident_type=DOCUMENT_LEFT_ON_DESK,
                        confidence=doc.confidence,
                        phone_bbox=doc.bbox,
                    )
                )

    return candidates


def _center_inside(
    bbox: tuple[int, int, int, int],
    zone: tuple[int, int, int, int],
) -> bool:
    """Check if the center of a bounding box is inside a zone rectangle."""
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
    """Find the nearest person to a phone if within proximity threshold.

    Returns the person Detection if the phone overlaps with a person or is
    within proximity_pixels edge-to-edge distance. Returns None otherwise.
    """
    # Check for overlap first (takes priority)
    for person in people:
        if _boxes_overlap(phone_bbox, person.bbox):
            return person

    # Check edge-to-edge distance from phone center to person boxes
    px, py = _bbox_center(phone_bbox)
    nearest: tuple[float, Detection] | None = None
    for person in people:
        distance = _distance_to_box(px, py, person.bbox)
        if distance <= proximity_pixels and (nearest is None or distance < nearest[0]):
            nearest = (distance, person)

    return nearest[1] if nearest else None


def _bbox_center(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    """Return the center point of a bounding box."""
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


def _boxes_overlap(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> bool:
    """Check if two bounding boxes overlap (have non-zero intersection area)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return max(ax1, bx1) < min(ax2, bx2) and max(ay1, by1) < min(ay2, by2)


def _distance_to_box(x: float, y: float, bbox: tuple[int, int, int, int]) -> float:
    """Calculate the minimum distance from a point to a bounding box edge."""
    x1, y1, x2, y2 = bbox
    dx = max(x1 - x, 0, x - x2)
    dy = max(y1 - y, 0, y - y2)
    return hypot(dx, dy)
