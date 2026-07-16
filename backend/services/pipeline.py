"""
Layout Generation Pipeline — Shared Service Controller
========================================================
Single-source-of-truth orchestration for the multi-floor blueprint generation
pipeline.  Both the REST endpoint (generate.py) and the WebSocket endpoint
(stream.py) delegate to ``run_generation_pipeline()`` rather than maintaining
duplicate copies of the 500+ line layout loop.

Phases 3.1 (scoped exceptions), 3.4 (composite seed hash), and 4.2
(de-duplication) are all addressed in this module.
"""

import copy
import hashlib
import math
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

from services.vastu_engine import assign_vastu_zones, calculate_vastu_score
from services.vastu_heatmap import (
    calculate_room_vastu_scores,
    apply_vastu_resizing,
    generate_vastu_heatmap,
)
from services.building_program import (
    BuildingProgram,
    create_building_program,
    generate_ground_floor_layout,
    generate_roof_floor_layout,
)
from services.circulation_engine import CirculationEngine
from services.structural_engine import StructuralEngine
from services.style_engine import detect_style, apply_style_constraints
from services.diff_engine import compute_diff
from services.site_context_engine import SiteContextEngine
from services.blueprint_scorer import score_blueprint
from services.solar_wind_engine import analyze_environment
from services.isometric_renderer import render_isometric
from services.proportion_validator import validate_proportions
from services.accessibility_engine import ensure_full_accessibility
from services.furniture_engine import place_furniture as FurnitureEngine
from services.constraint_solver import solve_layout as cpsat_solve_layout
from services.geometric_validator import validate_layout
from services.geometry_processor import find_door_positions
from services.schema_serializer import serialize_floor_plan

logger = logging.getLogger("plotit.pipeline")

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

FT_TO_M = 0.3048
M_TO_FT = 3.28084

# Minimum square-footage estimates for feasibility check
MIN_ESTIMATES = {
    "BEDROOM": 100, "BATHROOM": 35, "KITCHEN": 80,
    "DINING": 80, "LIVING": 120,
}


# ═══════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PipelineParams:
    """All inputs to the generation pipeline — a superset of what both
    the REST and WS endpoints accept."""

    plot_size_sqft: float
    floors: int = 1
    rooms: List[Dict] = field(default_factory=list)
    prompt: str = ""
    user_tier: str = "free"
    entry_direction: str = "N"
    has_lift: bool = False
    has_balcony: bool = False
    has_verandah: bool = False
    plot_width_ft: Optional[float] = None
    plot_depth_ft: Optional[float] = None
    building_type: str = "independent_house"
    architectural_style: Optional[str] = None
    original_unit_system: Optional[Dict[str, Any]] = None
    previous_layout: Optional[List[Dict[str, Any]]] = None
    enable_circulation: bool = True
    enable_heatmap: bool = True
    enable_structural: bool = True
    include_furniture: bool = True
    plot_shape: Optional[Dict[str, Any]] = None
    latitude: float = 12.0
    layout_mode: str = "cpsat"
    floor_number: int = 0

    # Async callback for streaming progress events.
    # Signature: async progress_callback(stage: str, progress: int, message: str)
    progress_callback: Optional[Callable[..., Coroutine]] = None


@dataclass
class PipelineResult:
    """Everything the pipeline produces."""
    response_data: Dict[str, Any]
    schema_blueprint: Dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _compute_layout_seed(p: PipelineParams) -> int:
    """Phase 3.4 — Composite seed hash.

    Includes ALL UI-togglable booleans and parameters so that changing
    ``has_lift``, ``floors``, ``entry_direction``, etc. without changing
    the prompt text still produces a different layout seed.
    """
    composite = "|".join([
        p.prompt,
        str(p.floors),
        str(p.has_lift),
        str(p.has_balcony),
        str(p.has_verandah),
        p.entry_direction,
        str(p.enable_circulation),
        str(p.plot_size_sqft),
    ])
    return int(hashlib.sha256(composite.encode()).hexdigest(), 16) % (2**32)


async def _emit_progress(callback, stage: str, progress: int, message: str):
    """Fire progress callback if one was provided (WS mode)."""
    if callback:
        await callback(stage, progress, message)


def _extract_dims_and_entry(prompt: str, plot_size: float, entry: str,
                            plot_w: Optional[float], plot_d: Optional[float]):
    """Extract WxD dimensions and entry direction from prompt text."""
    dim_match = re.search(r"(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)", prompt)
    if dim_match:
        w_val = float(dim_match.group(1))
        d_val = float(dim_match.group(2))
        if abs(w_val * d_val - plot_size) < 10:
            plot_w = w_val
            plot_d = d_val

    if entry == "N":
        p_lower = prompt.lower()
        if "entry south" in p_lower or "facing south" in p_lower:
            entry = "S"
        elif "entry east" in p_lower or "facing east" in p_lower:
            entry = "E"
        elif "entry west" in p_lower or "facing west" in p_lower:
            entry = "W"

    return plot_w, plot_d, entry


# ═══════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════

async def run_generation_pipeline(p: PipelineParams) -> PipelineResult:
    """
    Execute the full multi-floor blueprint generation pipeline.

    This is the *single* implementation of the layout loop, used by both
    ``routes/generate.py`` (REST) and ``routes/stream.py`` (WebSocket).

    Phases addressed here:
    - **3.1**: Each optional analysis engine is wrapped in a *scoped*
      try/except that catches only expected exceptions (ValueError,
      KeyError, TypeError) and logs with ``exc_info=True``.
    - **3.4**: ``layout_seed`` uses a composite hash of all UI booleans.
    - **4.2**: Eliminates the 400+ line duplication between routes.
    """
    cb = p.progress_callback

    # ── 0. Parse supplementary data from prompt ──────────────────────
    await _emit_progress(cb, "parsing", 5, "Parsing architectural requirements...")

    raw_rooms = list(p.rooms)

    # Style detection / application
    style_metadata = None
    active_style = p.architectural_style
    if not active_style:
        all_notes = " ".join(r.get("special_notes", "") or "" for r in raw_rooms)
        if all_notes.strip():
            active_style = detect_style(all_notes)
    if active_style:
        raw_rooms, style_metadata = apply_style_constraints(
            raw_rooms, active_style, p.plot_size_sqft
        )
        logger.info("Style applied: %s (%s)", active_style, style_metadata["display_name"])

    # Dimension & entry extraction from prompt text
    p.plot_width_ft, p.plot_depth_ft, p.entry_direction = _extract_dims_and_entry(
        p.prompt, p.plot_size_sqft, p.entry_direction,
        p.plot_width_ft, p.plot_depth_ft,
    )

    norm_btype = (p.building_type or "independent_house").lower().strip().replace(" ", "_")
    total_floors = max(p.floors, 1)

    plot_side = round(math.sqrt(p.plot_size_sqft), 1)
    plot_width = p.plot_width_ft or plot_side
    plot_depth = p.plot_depth_ft or plot_side

    # ── 1. Building Program ──────────────────────────────────────────
    await _emit_progress(cb, "building_program", 20, "Enriching room program with mandatory elements...")

    program = create_building_program(
        plot_area=p.plot_size_sqft,
        user_rooms=raw_rooms,
        building_type=norm_btype,
        floor_number=p.floor_number,
        floors_total=total_floors,
        entry_direction=p.entry_direction,
        has_lift=p.has_lift,
        has_balcony=p.has_balcony,
        has_verandah=p.has_verandah,
        plot_width=plot_width,
        plot_depth=plot_depth,
    )
    enriched_rooms = program.get_enriched_rooms()
    program_meta = program.get_metadata()

    logger.info(
        "BuildingProgram: %s, %s, %d rooms",
        program_meta["building_type"],
        program_meta["floor_label"],
        program_meta["total_rooms"],
    )

    # ── 2. Vastu Engine ──────────────────────────────────────────────
    core_fn = 1 if total_floors > 1 else 0
    vastu_rooms = program.get_floor_program(core_fn, total_floors)
    vastu_assignments = assign_vastu_zones(vastu_rooms)
    vastu_results = calculate_vastu_score(vastu_assignments)

    # ── 3. Site Context ──────────────────────────────────────────────
    await _emit_progress(cb, "site_context", 30, "Calculating setbacks and buildable envelope...")

    site_engine = SiteContextEngine()
    site_context = site_engine.calculate_buildable_envelope(
        plot_width_m=plot_width * FT_TO_M,
        plot_depth_m=plot_depth * FT_TO_M,
        road_width_m=8.534,
        entry_direction=p.entry_direction,
        common_passage_m=0.0,
        passage_side=None,
        building_type=p.building_type,
    )

    bw_ft = round(site_context["buildable_width"] * M_TO_FT, 2)
    bd_ft = round(site_context["buildable_depth"] * M_TO_FT, 2)
    ox_ft = round(site_context["buildable_x"] * M_TO_FT, 2)
    oy_ft = round(site_context["buildable_y"] * M_TO_FT, 2)

    logger.info(
        "Site Context: buildable %.1fx%.1f ft (coverage %s%%)",
        bw_ft, bd_ft, site_context["ground_coverage_pct"],
    )

    # ── 4. Feasibility Check ─────────────────────────────────────────
    buildable_area_sqft = bw_ft * bd_ft
    for check_fn in range(min(max(p.floors, 1), 2)):
        floor_check_rooms = [
            r for r in program.get_floor_program(check_fn, max(p.floors, 1))
            if not r.get("is_external", False)
        ]
        floor_min_required = sum(
            MIN_ESTIMATES.get(r["type"].upper(), 50) * (r.get("count") or 1)
            for r in floor_check_rooms
        )
        if floor_min_required > buildable_area_sqft * 0.95:
            raise ValueError(
                f"Floor {check_fn} layout too large ({floor_min_required} sqft min) "
                f"for the buildable plot area ({round(buildable_area_sqft, 1)} sqft after setbacks)."
            )

    # ── 5. Multi-Floor Sequential Pipeline ───────────────────────────
    await _emit_progress(cb, "layout", 50, "Generating all floor plans...")

    layout_seed = _compute_layout_seed(p)
    shape_config = dict(p.plot_shape or {"type": "rectangle"})
    shape_config["width"] = bw_ft
    shape_config["depth"] = bd_ft

    roof_floor_num = total_floors
    all_floor_layouts: Dict[int, List[Dict]] = {}
    bsp_engine = None
    fixed_positions: Dict[str, Dict] = {}
    is_independent = norm_btype in ("independent_house", "villa", "row_house")

    for floor_num in range(total_floors + 1):  # 0=ground … total_floors=roof
        floor_rooms = program.get_floor_program(floor_num, total_floors)
        internal_rooms = [r for r in floor_rooms if not r.get("is_external", False)]
        external_rooms = [r for r in floor_rooms if r.get("is_external", False)]

        if floor_num == 0 and total_floors > 1 and not is_independent:
            # ── GROUND FLOOR: parking + utilities (stilt) ────────────
            floor_layout = generate_ground_floor_layout(
                bw_ft, bd_ft, has_lift=p.has_lift,
            )
            for room in floor_layout:
                room["x"] = round(room.get("x", 0) + ox_ft, 2)
                room["y"] = round(room.get("y", 0) + oy_ft, 2)

            for r in floor_layout:
                rtype = r["type"].lower()
                if rtype in ["staircase", "lift", "stair_room"]:
                    fixed_positions[rtype] = {
                        "x": round(r["x"] - ox_ft, 2),
                        "y": round(r["y"] - oy_ft, 2),
                        "width": r["width"],
                        "height": r["height"],
                    }
            all_floor_layouts[floor_num] = floor_layout

        elif floor_num == roof_floor_num:
            # ── ROOF FLOOR ───────────────────────────────────────────
            floor_layout = generate_roof_floor_layout(
                bw_ft, bd_ft,
                has_lift=p.has_lift,
                roof_floor_num=roof_floor_num,
                fixed_positions=fixed_positions,
            )
            for room in floor_layout:
                room["x"] = round(room.get("x", 0) + ox_ft, 2)
                room["y"] = round(room.get("y", 0) + oy_ft, 2)

            for r in floor_layout:
                rtype = r["type"].lower()
                if rtype in ["staircase", "lift", "stair_room"]:
                    key = "staircase" if rtype == "stair_room" else rtype
                    if key in fixed_positions:
                        pos = fixed_positions[key]
                        r["x"] = round(pos["x"] + ox_ft, 2)
                        r["y"] = round(pos["y"] + oy_ft, 2)
                        r["width"] = pos["width"]
                        r["height"] = pos["height"]
            all_floor_layouts[floor_num] = floor_layout

        else:
            # ── TYPICAL RESIDENTIAL FLOOR ────────────────────────────
            if floor_num > 1 and 1 in all_floor_layouts:
                floor_layout = copy.deepcopy(all_floor_layouts[1])
                for room in floor_layout:
                    room["floor"] = floor_num
                all_floor_layouts[floor_num] = floor_layout
            else:
                # CP-SAT Constraint Solver
                floor_vastu = {}
                for room in floor_rooms:
                    rid = room.get("id", "")
                    if rid:
                        floor_vastu[rid] = vastu_assignments.get(rid, "C")

                solver_result = cpsat_solve_layout(
                    plot_width_ft=bw_ft,
                    plot_height_ft=bd_ft,
                    rooms=internal_rooms,
                    vastu_assignments=floor_vastu,
                    entry_direction=p.entry_direction,
                    max_time_seconds=5.0,
                    fixed_positions=fixed_positions,
                    floor_number=floor_num,
                    random_seed=layout_seed % (2**31),
                )
                floor_layout = solver_result["rooms"]

                if floor_num == 0:
                    for r in floor_layout:
                        rtype = r["type"].lower()
                        if rtype in ["staircase", "lift", "stairs"]:
                            key = "staircase" if rtype == "stairs" else rtype
                            fixed_positions[key] = {
                                "x": round(r["x"], 2),
                                "y": round(r["y"], 2),
                                "width": r["width"],
                                "height": r["height"],
                            }

                # Place external rooms in setbacks
                for i, ext in enumerate(external_rooms):
                    ext_y = bd_ft + (2.0 if i == 0 else 6.0)
                    ext_x = 2.0
                    floor_layout.append({
                        **ext,
                        "id": f"{ext['type']}_{floor_num}",
                        "x": round(ext_x + ox_ft, 2),
                        "y": round(ext_y + oy_ft, 2),
                        "width": 6.0, "height": 4.0,
                        "area": 24.0, "floor": floor_num,
                        "is_external_placed": True,
                        "is_annotation": True,
                    })

                # Apply setback offsets
                for room in floor_layout:
                    if not room.get("is_external_placed"):
                        room["x"] = round(room.get("x", 0) + ox_ft, 2)
                        room["y"] = round(room.get("y", 0) + oy_ft, 2)
                    room["floor"] = floor_num

                # Validate
                validation = validate_layout(floor_layout, bw_ft, bd_ft)
                logger.info(
                    "Floor %d solver: status=%s, time=%dms, coverage=%s%%, overlaps=%d, valid=%s",
                    floor_num, solver_result["status"],
                    solver_result["solve_time_ms"],
                    solver_result["coverage_pct"],
                    validation["overlap_count"],
                    validation["is_valid"],
                )
                bsp_engine = f"cpsat_{solver_result['status'].lower()}"
                all_floor_layouts[floor_num] = floor_layout

    # ── 6. Determine Primary Layout ──────────────────────────────────
    primary_fn = 1 if total_floors > 1 else 0
    placed_rooms = all_floor_layouts.get(primary_fn, all_floor_layouts.get(0, []))
    if not placed_rooms:
        raise ValueError("Solver failed to generate a valid layout. Please check constraints.")

    # ── 7. Analysis Engines ──────────────────────────────────────────
    await _emit_progress(cb, "analysis", 75, "Analyzing architectural performance...")

    # Phase 3.1 — Scoped exceptions with exc_info=True
    circulation_data = None
    if p.enable_circulation:
        try:
            circ_engine = CirculationEngine(plot_width, plot_depth)
            circulation_data = circ_engine.find_optimal_corridors(placed_rooms)
        except (ValueError, TypeError, KeyError) as circ_err:
            logger.error("Circulation engine failed: %s", circ_err, exc_info=True)
            circulation_data = {
                "efficiency_score": 0, "corridors": [],
                "total_corridor_area": 0, "notes": "Engine failed",
            }

    # Floor labels
    unique_labels: Dict[int, str] = {}
    r_keys = sorted(all_floor_layouts.keys())
    for fn in r_keys:
        if fn == 0:
            unique_labels[fn] = "GROUND"
        elif fn == r_keys[-1] and len(r_keys) > 1:
            unique_labels[fn] = "ROOF"
        else:
            unique_labels[fn] = (
                f"{fn}ST" if fn == 1 else
                (f"{fn}ND" if fn == 2 else f"{fn}TH")
            )

    final_floor_layouts: Dict[int, List[Dict]] = {}
    final_labels: Dict[int, str] = {}
    seen_lbls: set = set()
    for fn in r_keys:
        lbl = unique_labels.get(fn, f"F{fn}")
        if lbl in seen_lbls:
            continue
        seen_lbls.add(lbl)
        final_floor_layouts[fn] = all_floor_layouts[fn]
        final_labels[fn] = lbl

    # Structural
    struct_engine = StructuralEngine(plot_width, plot_depth)
    structural_data = None

    # Accessibility & Doors
    try:
        initial_doors = find_door_positions(placed_rooms, program)
        updated_doors, accessibility_report = ensure_full_accessibility(
            placed_rooms,
            doors=initial_doors,
            entry_direction=p.entry_direction,
        )
    except (ValueError, TypeError, KeyError) as acc_err:
        logger.error("Accessibility engine failed: %s", acc_err, exc_info=True)
        updated_doors = []
        accessibility_report = {"connected": False, "issues": ["Engine failed"]}

    # Furniture
    furniture_placements = []
    if p.include_furniture:
        try:
            furniture_placements = FurnitureEngine(placed_rooms, updated_doors)
        except (ValueError, TypeError, KeyError) as furn_err:
            logger.error("Furniture engine failed: %s", furn_err, exc_info=True)

    # ── 8. Per-Floor Rendering ───────────────────────────────────────
    await _emit_progress(cb, "rendering", 90, "Rendering professional blueprints for all floors...")

    final_floor_schemas: Dict[int, Dict] = {}
    unit_sys = "metric" if (
        p.original_unit_system and p.original_unit_system.get("system") == "metric"
    ) else "imperial"

    for fn, floor_rooms_list in final_floor_layouts.items():
        # Per-floor structural analysis
        try:
            floor_structural_analysis = struct_engine.analyze(floor_rooms_list)
            if fn == 1 or (fn == 0 and structural_data is None):
                structural_data = floor_structural_analysis
        except (ValueError, TypeError, KeyError) as struct_err:
            logger.error("Structural analysis failed for floor %d: %s", fn, struct_err, exc_info=True)
            floor_structural_analysis = {
                "columns": [], "beams": [],
                "wall_boundary": {"geometry": None},
            }

        # Schema serialization
        try:
            schema = serialize_floor_plan(
                placed_rooms=floor_rooms_list,
                plot_width=plot_width,
                plot_height=plot_depth,
                vastu_score=vastu_results,
                building_program=program,
                floor_number=fn,
                shape_config=shape_config,
                heavy_elements=floor_structural_analysis,
                furniture_items=(
                    furniture_placements if fn >= 1 and fn <= total_floors else []
                ),
                unit_system=unit_sys,
                solver_time_ms=0,
            )
            final_floor_schemas[fn] = schema
        except Exception as schema_err:
            logger.error("JSON serialization failed for floor %d: %s", fn, schema_err, exc_info=True)
            if fn == (1 if total_floors > 1 else 0):
                raise ValueError(f"Core floor serialization failed: {str(schema_err)}")
            final_floor_schemas[fn] = {}

    schema_blueprint = final_floor_schemas.get(
        core_fn, final_floor_schemas.get(0, {})
    )

    # ── 9. Optional Analysis Passes ──────────────────────────────────

    # Proportion Validator
    proportion_data = {"proportion_score": 0.0, "errors": 0, "warnings": 0, "flagged": []}
    try:
        proportion_data = validate_proportions(placed_rooms)
    except (ValueError, TypeError, KeyError) as prop_err:
        logger.error("Proportion validation failed: %s", prop_err, exc_info=True)

    # Blueprint Scorer
    blueprint_score = {"overall": 0.0, "grade": "N/A", "label": "Analysis Pending", "axes": {}}
    try:
        blueprint_score = score_blueprint(
            placed_rooms, plot_width, plot_depth,
            vastu_score=vastu_results,
            accessibility_report=accessibility_report,
            proportion_report=proportion_data,
        )
    except (ValueError, TypeError, KeyError) as score_err:
        logger.error("Blueprint scoring failed: %s", score_err, exc_info=True)

    # Solar & Wind
    environment_data: Dict[str, Any] = {
        "overall_sun_score": 0, "overall_vent_score": 0,
        "solar_points": [], "vent_points": [],
    }
    try:
        environment_data = analyze_environment(
            placed_rooms, plot_width, plot_depth,
            latitude=p.latitude,
        )
    except (ValueError, TypeError, KeyError) as env_err:
        logger.error("Environment analysis failed: %s", env_err, exc_info=True)

    # Isometric 3D
    iso_svg = None
    try:
        iso_svg = render_isometric(
            placed_rooms, plot_width, plot_depth,
            style=active_style if active_style else "residential",
        )
    except (ValueError, TypeError, KeyError) as iso_err:
        logger.error("Isometric render failed: %s", iso_err, exc_info=True)

    # Refinement Diff
    diff_result = None
    if p.previous_layout:
        try:
            diff = compute_diff(p.previous_layout, placed_rooms)
            diff_result = diff.to_dict()
        except (ValueError, TypeError, KeyError) as diff_err:
            logger.error("Diff engine failed: %s", diff_err, exc_info=True)

    # Vastu Heatmap
    room_scores: Dict[str, Any] = {}
    vastu_heatmap_data = {"cells": [], "resolution_ft": 4, "avg_score": 0}
    try:
        room_scores = calculate_room_vastu_scores(placed_rooms, vastu_assignments)
        vastu_heatmap_data = generate_vastu_heatmap(
            placed_rooms, room_scores,
            plot_width=plot_width, plot_height=plot_depth,
        )
    except (ValueError, TypeError, KeyError) as hm_err:
        logger.error("Vastu heatmap failed: %s", hm_err, exc_info=True)

    # ── 10. Assemble Response ────────────────────────────────────────

    response_data: Dict[str, Any] = {
        "seed": layout_seed,
        "vastu_score": vastu_results["score"],
        "vastu_label": vastu_results["label"],
        "vastu_color": vastu_results["color"],
        "dimensions": [plot_width, plot_depth],
        "engine": bsp_engine or "cpsat_v4",
        "floor_label": program_meta["floor_label"],
        "building_type": program_meta["building_type"],
        "rooms_placed": len(placed_rooms),
        "floors_generated": len(all_floor_layouts),

        "floor_labels": {str(fn): lbl for fn, lbl in final_labels.items()},
        "all_floor_layouts": {
            str(fn): rooms for fn, rooms in final_floor_layouts.items()
        },

        "circulation": circulation_data,
        "vastu_heatmap": vastu_heatmap_data,
        "room_vastu_scores": room_scores,
        "architectural_style": style_metadata,
        "layout_diff": diff_result,
        "current_layout": placed_rooms,
        "structural": structural_data,
        "site_context": {
            k: v for k, v in site_context.items() if k != "buildable_polygon"
        },
        "blueprint_score": blueprint_score,
        "environment": environment_data,
        "isometric_svg": iso_svg,
        "proportions": proportion_data,
        "accessibility_report": accessibility_report,
        "alternative_svg": None,

        # Schema-based floor plans (JSON mode)
        "floor_plan": schema_blueprint,
        "floor_plans": {str(fn): schema for fn, schema in final_floor_schemas.items()},
    }

    return PipelineResult(
        response_data=response_data,
        schema_blueprint=schema_blueprint,
    )
