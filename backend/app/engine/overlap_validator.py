from __future__ import annotations


INCOMPATIBLE_TYPES: dict[str, list[str]] = {
    "water": ["town", "castle", "farmland", "cave_entrance", "dungeon"],
    "town_buildings": ["lake", "farmland", "cave_entrance"],
    "castle_grounds": ["lake", "farmland"],
    "cave_mouth": ["castle", "town_buildings"],
    "dungeon_walls": ["lake"],
}

OVERLAP_THRESHOLD = 0.3


def _rects_overlap(
    a: dict[str, float],
    b: dict[str, float],
    a_pos: dict[str, float],
    b_pos: dict[str, float],
) -> bool:
    ax1 = a_pos["x"] - a.get("width", 0) / 2
    ax2 = a_pos["x"] + a.get("width", 0) / 2
    ay1 = a_pos["y"] - a.get("height", 0) / 2
    ay2 = a_pos["y"] + a.get("height", 0) / 2

    bx1 = b_pos["x"] - b.get("width", 0) / 2
    bx2 = b_pos["x"] + b.get("width", 0) / 2
    by1 = b_pos["y"] - b.get("height", 0) / 2
    by2 = b_pos["y"] + b.get("height", 0) / 2

    overlap_x = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    overlap_y = max(0.0, min(ay2, by2) - max(ay1, by1))

    if overlap_x <= 0 or overlap_y <= 0:
        return False

    a_area = (ax2 - ax1) * (ay2 - ay1)
    b_area = (bx2 - bx1) * (by2 - by1)
    overlap_area = overlap_x * overlap_y

    smaller_area = min(a_area, b_area)
    if smaller_area <= 0:
        return False

    return (overlap_area / smaller_area) > OVERLAP_THRESHOLD


def _circle_rect_overlap(
    circle: dict[str, float],
    rect: dict[str, float],
    circle_pos: dict[str, float],
    rect_pos: dict[str, float],
) -> bool:
    cx, cy = circle_pos["x"], circle_pos["y"]
    r = circle.get("radius", circle.get("width", 0) / 2)

    rx1 = rect_pos["x"] - rect.get("width", 0) / 2
    rx2 = rect_pos["x"] + rect.get("width", 0) / 2
    ry1 = rect_pos["y"] - rect.get("height", 0) / 2
    ry2 = rect_pos["y"] + rect.get("height", 0) / 2

    nearest_x = max(rx1, min(cx, rx2))
    nearest_y = max(ry1, min(cy, ry2))

    dx = cx - nearest_x
    dy = cy - nearest_y
    return (dx * dx + dy * dy) < (r * r)


def _zones_overlap(
    excl_zone: dict[str, float],
    target_footprint: dict[str, float],
    excl_pos: dict[str, float],
    target_pos: dict[str, float],
) -> bool:
    excl_shape = excl_zone.get("shape", "polygon")
    target_shape = target_footprint.get("shape", "polygon")

    has_circle = excl_shape == "circle" or target_shape == "circle"
    has_ellipse = excl_shape == "ellipse" or target_shape == "ellipse"

    if has_circle and not has_ellipse:
        circle = excl_zone if excl_shape == "circle" else target_footprint
        rect = target_footprint if excl_shape == "circle" else excl_zone
        circle_pos = excl_pos if excl_shape == "circle" else target_pos
        rect_pos = target_pos if excl_shape == "circle" else excl_pos
        return _circle_rect_overlap(circle, rect, circle_pos, rect_pos)

    if excl_shape in ("polygon", "rectangle", "ellipse") and target_shape in ("polygon", "rectangle", "ellipse"):
        return _rects_overlap(excl_zone, target_footprint, excl_pos, target_pos)

    if excl_shape == "none" or target_shape == "none":
        return False

    return _rects_overlap(excl_zone, target_footprint, excl_pos, target_pos)


def validate_structure_placement(
    new_structure: dict,
    existing_structures: list[dict],
) -> tuple[bool, list[str]]:
    rejections: list[str] = []
    excl_zone = new_structure.get("exclusion_zone", {})
    excl_reason = excl_zone.get("reason", "")
    new_pos = new_structure.get("position", {"x": 0, "y": 0})
    new_footprint = new_structure.get("footprint", {})
    new_layer = new_structure.get("layer")

    for existing in existing_structures:
        if existing.get("layer") != new_layer:
            continue

        existing_excl = existing.get("exclusion_zone", {})
        existing_reason = existing_excl.get("reason", "")
        existing_pos = existing.get("position", {"x": 0, "y": 0})
        existing_footprint = existing.get("footprint", {})

        if excl_reason and existing_reason:
            if _zones_overlap(excl_zone, existing_excl, new_pos, existing_pos):
                rejections.append(
                    f"'{new_structure['id']}' exclusion zone conflicts with '{existing['id']}' "
                    f"exclusion zone (reason: {existing_reason})"
                )

        incompatible_reasons = INCOMPATIBLE_TYPES.get(existing_reason, [])
        if new_structure.get("type") in incompatible_reasons:
            if _zones_overlap(new_footprint, existing_excl, new_pos, existing_pos):
                rejections.append(
                    f"'{new_structure['id']}' (type {new_structure.get('type')}) is incompatible "
                    f"with '{existing['id']}' exclusion zone (reason: {existing_reason})"
                )

        existing_incompatible = INCOMPATIBLE_TYPES.get(excl_reason, [])
        if existing.get("type") in existing_incompatible:
            if _zones_overlap(existing_footprint, excl_zone, existing_pos, new_pos):
                rejections.append(
                    f"'{existing['id']}' (type {existing.get('type')}) is incompatible "
                    f"with '{new_structure['id']}' exclusion zone (reason: {excl_reason})"
                )

    return len(rejections) == 0, rejections


def validate_world(world_data: dict) -> tuple[bool, list[str]]:
    all_rejections: list[str] = []
    structures = world_data.get("structures", [])

    for i, struct in enumerate(structures):
        others = [s for j, s in enumerate(structures) if j != i]
        ok, reasons = validate_structure_placement(struct, others)
        if not ok:
            all_rejections.extend(reasons)

    return len(all_rejections) == 0, all_rejections
