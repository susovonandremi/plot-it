"""
Generation Route — v3.0 (Architectural Masterclass)
====================================================
Handles the end-to-end blueprint generation pipeline:

  v2.0 Features:
  A. Adaptive Circulation Graphs (A* corridor pathfinding)
  B. Vastu 2.0 (per-room energy scores + heatmap)
  C. Architectural Style Presets (Kerala, Minimalist, Mughal, etc.)
  D. Refinement Diffing (compare old vs new layout, surgical SVG patching)
  E. Structural Engineering Layer (columns, beams, load-bearing walls)

  v3.0 Features:
  F. Door Accessibility Graph (BFS verification + auto-fix)
  G. Room Proportion Validator (aspect ratio quality)
  H. Furniture Synthesis Engine (auto-placed furniture)
  I. Blueprint Scoring Dashboard (5-axis quality score)
  J. Solar & Wind Intelligence (sun exposure + ventilation)
  K. Isometric 3D Preview (2.5D SVG extrusion)
  L. Material Textures, Shadows, Typography (auto in SVG renderer)
"""

import copy
import math
import logging
import re
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from services.vastu_engine import assign_vastu_zones, calculate_vastu_score
from services.vastu_heatmap import calculate_room_vastu_scores, apply_vastu_resizing, generate_vastu_heatmap
from services.professional_svg_renderer import render_blueprint_professional
from services.building_program import BuildingProgram, create_building_program, generate_ground_floor_layout, generate_roof_floor_layout
from services.circulation_engine import CirculationEngine
from services.structural_engine import StructuralEngine
from services.style_engine import detect_style, apply_style_constraints, get_all_style_names
from services.diff_engine import compute_diff
from services.site_context_engine import SiteContextEngine

# v3.0 imports
from services.blueprint_scorer import score_blueprint
from services.solar_wind_engine import analyze_environment
from services.isometric_renderer import render_isometric
from services.proportion_validator import validate_proportions
from services.accessibility_engine import ensure_full_accessibility
from services.furniture_engine import place_furniture as FurnitureEngine
from limiter import limiter
from services.project_store import save_project

# v4.0: CP-SAT Constraint Solver (replaces ArchitecturalCoreSolver)
from services.constraint_solver import solve_layout as cpsat_solve_layout
from services.geometric_validator import validate_layout

logger = logging.getLogger("plotai")
router = APIRouter()


# ── REQUEST MODELS ────────────────────────────────────────────────────────────

class RoomConfig(BaseModel):
    type: str
    count: Optional[int] = 1
    special_notes: Optional[str] = None


class PlotShapeConfig(BaseModel):
    type: str = "rectangle"
    cutout_width: Optional[float] = None
    cutout_height: Optional[float] = None
    cutout_corner: str = "NE"


class GenerateRequest(BaseModel):
    plot_size_sqft: float = Field(..., gt=0, lt=100000)
    floors: int = 1
    rooms: List[RoomConfig]
    user_tier: str = "free"
    original_unit_system: Optional[Dict[str, Any]] = None

    # Building context
    building_type: str = "independent_house"
    floor_number: int = 0
    entry_direction: str = "N"
    latitude: float = 12.0  # Default: South India
    has_lift: bool = False
    has_balcony: bool = False
    has_verandah: bool = False
    plot_width_ft: Optional[float] = None
    plot_depth_ft: Optional[float] = None
    plot_shape: Optional[PlotShapeConfig] = None

    # Feature C: Style preset
    architectural_style: Optional[str] = None

    # Feature D: Refinement diffing
    previous_layout: Optional[List[Dict[str, Any]]] = None

    # Feature flags (allow clients to opt-in/out of expensive features)
    enable_circulation: bool = True
    enable_heatmap: bool = True
    enable_structural: bool = True

    # v3.0: Layout mode — 'cpsat' (default)
    layout_mode: str = "cpsat"
    include_furniture: bool = True
    prompt: str = Field(..., min_length=10, max_length=2000)

# ── MAIN ENDPOINT ─────────────────────────────────────────────────────────────

@router.post("/generate")
@limiter.limit("10/minute")
async def generate_blueprint_endpoint(request: Request, request_data: GenerateRequest):
    """
    End-to-end pipeline:
      Style → BuildingProgram → Vastu → BSP Layout →
      Circulation → Structural → Heatmap → SVG → Diff
    """
    pass
    try:
        raw_rooms = [r.dict() for r in request_data.rooms]

        # ── FEATURE C: Apply Style Constraints ───────────────────────────────
        style_metadata = None
        active_style = request_data.architectural_style

        # Auto-detect style if not explicitly provided (from special_notes or future prompt field)
        if not active_style:
            # Try detecting from room special_notes as a fallback
            all_notes = " ".join(r.get("special_notes", "") or "" for r in raw_rooms)
            if all_notes.strip():
                active_style = detect_style(all_notes)

        if active_style:
            raw_rooms, style_metadata = apply_style_constraints(
                raw_rooms, active_style, request_data.plot_size_sqft
            )
            logger.info(f"Style applied: {active_style} ({style_metadata['display_name']})")

        # Smart extraction: "40x60", "30x50", etc.
        prompt_text = request_data.prompt or ""
        dim_match = re.search(r"(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)", prompt_text)
        if dim_match:
             w_val = float(dim_match.group(1))
             d_val = float(dim_match.group(2))
             # Match to plot_size if possible
             if abs(w_val * d_val - request_data.plot_size_sqft) < 10:
                  request_data.plot_width_ft = w_val
                  request_data.plot_depth_ft = d_val
        
        # Entry direction extraction
        if request_data.entry_direction == "N": # ONLY if default
             p_lower = prompt_text.lower()
             if "entry south" in p_lower or "facing south" in p_lower: request_data.entry_direction = "S"
             elif "entry east" in p_lower or "facing east" in p_lower: request_data.entry_direction = "E"
             elif "entry west" in p_lower or "facing west" in p_lower: request_data.entry_direction = "W"

        # Normalize building type for reliable comparison
        norm_btype = (request_data.building_type or "independent_house").lower().strip().replace(" ", "_")
        
        # G+1 override: independent houses with bedrooms are always at least 2 floors
        if norm_btype in ("independent_house", "villa", "row_house") and request_data.floors <= 1:
            total_floors = 2
        else:
            total_floors = max(request_data.floors, 1)
        
        # Clamp roof floor number to total_floors
        roof_floor_num = total_floors   # 0=ground, 1..total_floors-1=residential, total_floors=roof

        plot_side = round(math.sqrt(request_data.plot_size_sqft), 1)
        plot_width = request_data.plot_width_ft or plot_side
        plot_depth = request_data.plot_depth_ft or plot_side

        program = create_building_program(
            plot_area=request_data.plot_size_sqft,
            user_rooms=raw_rooms,
            building_type=norm_btype,    # use normalized type, not raw request_data.building_type
            floor_number=request_data.floor_number,
            floors_total=total_floors,
            entry_direction=request_data.entry_direction,
            has_lift=request_data.has_lift,
            has_balcony=request_data.has_balcony,
            has_verandah=request_data.has_verandah,
            plot_width=plot_width,
            plot_depth=plot_depth,
        )

        enriched_rooms = program.get_enriched_rooms()
        program_meta = program.get_metadata()

        print(f"🏛️ BuildingProgram: {program_meta['building_type']}, "
              f"{program_meta['floor_label']}, "
              f"{program_meta['total_rooms']} rooms")

        # ── VASTU ENGINE ──────────────────────────────────────────────────────
        # For 1-story: Floor 0 has residentials. For Multi-story: Floor 1 is core.
        core_fn = 1 if total_floors > 1 else 0
        vastu_rooms = program.get_floor_program(core_fn, total_floors)
        vastu_assignments = assign_vastu_zones(vastu_rooms)
        vastu_results = calculate_vastu_score(vastu_assignments)

        # ── FEASIBILITY CHECK ─────────────────────────────────────────────────
        MIN_ESTIMATES = {"BEDROOM": 100, "BATHROOM": 35, "KITCHEN": 80, "DINING": 80, "LIVING": 120}
        total_min_required = sum(
            MIN_ESTIMATES.get(r["type"].upper(), 50) * (r.get("count") or 1)
            for r in enriched_rooms
        )
        if total_min_required > request_data.plot_size_sqft * 0.95:
            raise HTTPException(
                status_code=400,
                detail=f"Layout too large ({total_min_required} sqft min) for plot ({request_data.plot_size_sqft} sqft)."
            )

        # ── SITE CONTEXT ENGINE ────────────────────────────────────────────────
        # Calculate buildable envelope BEFORE layout begins
        FT_TO_M = 0.3048
        M_TO_FT = 3.28084
        site_engine = SiteContextEngine()
        site_context = site_engine.calculate_buildable_envelope(
            plot_width_m=plot_width * FT_TO_M,
            plot_depth_m=plot_depth * FT_TO_M,
            road_width_m=8.534,  # default 28 ft road from blueprint
            entry_direction=request_data.entry_direction,
            common_passage_m=0.0,
            passage_side=None,
            building_type=request_data.building_type,
        )

        # Use buildable dimensions (in feet) for layout instead of raw plot
        buildable_width_ft = round(site_context['buildable_width'] * M_TO_FT, 2)
        buildable_depth_ft = round(site_context['buildable_depth'] * M_TO_FT, 2)
        setback_offset_x_ft = round(site_context['buildable_x'] * M_TO_FT, 2)
        setback_offset_y_ft = round(site_context['buildable_y'] * M_TO_FT, 2)

        print(f"📐 Site Context: buildable {buildable_width_ft}x{buildable_depth_ft} ft "
              f"(coverage {site_context['ground_coverage_pct']}%), "
              f"setbacks F={site_context['setbacks']['front']}m "
              f"R={site_context['setbacks']['rear']}m "
              f"L={site_context['setbacks']['left']}m "
              f"R={site_context['setbacks']['right']}m")

        # ══════════════════════════════════════════════════════════════════════
        # MULTI-FLOOR SEQUENTIAL PIPELINE
        # Ground ≠ Typical 1st-Nth ≠ Roof  (mirrors real blueprint sheets)
        # ══════════════════════════════════════════════════════════════════════

        layout_seed = int(__import__('hashlib').sha256(request_data.prompt.encode()).hexdigest(), 16) % (2**32)
        shape_config = request_data.plot_shape.dict() if request_data.plot_shape else {"type": "rectangle"}
        shape_config["width"] = buildable_width_ft
        shape_config["depth"] = buildable_depth_ft

        # Ground=0, 1st=1, ... Roof=total_floors
        # Example G+1: floors=2 -> 0, 1 (Residential), 2 (Roof). Loop range(3).
        roof_floor_num = total_floors 
        
        all_floor_layouts: Dict[int, List[Dict]] = {}
        floor_svgs: Dict[int, str] = {}
        bsp_engine = None  # will be set for typical floor

        # Track fixed positions for vertical alignment (stairs, lift) across floors
        fixed_positions = {}

        for floor_num in range(total_floors + 1):  # 0=ground … total_floors=roof
            # ── Get floor-specific room program ───────────────────────────
            floor_rooms = program.get_floor_program(floor_num, total_floors)
            
            # Filter out external rooms (Sump/Septic) to place in setbacks later
            internal_rooms = [r for r in floor_rooms if not r.get('is_external', False)]
            external_rooms = [r for r in floor_rooms if r.get('is_external', False)]

            # Ground floor: stilt layout if non-independent multi-story, else full CPSAT
            is_independent = norm_btype in ("independent_house", "villa", "row_house")
            if floor_num == 0 and total_floors > 1 and not is_independent:
                # ── GROUND FLOOR: parking + utilities (fixed positions) ───
                floor_layout = generate_ground_floor_layout(
                    buildable_width_ft, buildable_depth_ft,
                    has_lift=request_data.has_lift,
                )
                # Apply setback offsets
                for room in floor_layout:
                    room['x'] = round(room.get('x', 0) + setback_offset_x_ft, 2)
                    room['y'] = round(room.get('y', 0) + setback_offset_y_ft, 2)

                # Capture staircase/lift position for upper floor alignment
                for r in floor_layout:
                    rtype = r['type'].lower()
                    if rtype in ['staircase', 'lift', 'stair_room']:
                        fixed_positions[rtype] = {
                            'x': round(r['x'] - setback_offset_x_ft, 2),
                            'y': round(r['y'] - setback_offset_y_ft, 2),
                            'width': r['width'],
                            'height': r['height']
                        }

                all_floor_layouts[floor_num] = floor_layout
                print(f"🅿️ Ground floor (Stilt): {len(floor_layout)} elements")
            elif floor_num == roof_floor_num:
                # ── ROOF FLOOR: OHWR + terrace + machine room ─────────────
                floor_layout = generate_roof_floor_layout(
                    buildable_width_ft, buildable_depth_ft,
                    has_lift=request_data.has_lift,
                    roof_floor_num=roof_floor_num,
                    fixed_positions=fixed_positions,
                )
                for room in floor_layout:
                    room['x'] = round(room.get('x', 0) + setback_offset_x_ft, 2)
                    room['y'] = round(room.get('y', 0) + setback_offset_y_ft, 2)
                
                # Ensure Roof staircase alignment (apply setbacks to fixed_positions)
                for r in floor_layout:
                    rtype = r['type'].lower()
                    if rtype in ['staircase', 'lift', 'stair_room']:
                        key = 'staircase' if rtype == 'stair_room' else rtype
                        if key in fixed_positions:
                            pos = fixed_positions[key]
                            r['x'] = round(pos['x'] + setback_offset_x_ft, 2)
                            r['y'] = round(pos['y'] + setback_offset_y_ft, 2)
                            r['width'] = pos['width']
                            r['height'] = pos['height']

                all_floor_layouts[floor_num] = floor_layout
                print(f"🏠 Roof floor: {len(floor_layout)} elements (OHWR/terrace)")

            else:
                # ── TYPICAL RESIDENTIAL FLOOR ─────────────────────────────
                # Floors 2+ are identical deep-copies of floor 1 (blueprint TYP.)
                if floor_num > 1 and 1 in all_floor_layouts:
                    floor_layout = copy.deepcopy(all_floor_layouts[1])
                    for room in floor_layout:
                        room['floor'] = floor_num
                    all_floor_layouts[floor_num] = floor_layout
                    print(f"📋 Floor {floor_num}: cloned from floor 1 ({len(floor_layout)} rooms)")
                else:
                    # ── CP-SAT CONSTRAINT SOLVER (v4.0) ──────────────────────
                    # Replaces all heuristic layout engines.
                    # Works in feet natively — no M_TO_FT conversion needed.

                    # Build Vastu assignments for this floor's rooms
                    floor_vastu = {}
                    for room in floor_rooms:
                        rid = room.get('id', '')
                        if rid:
                            floor_vastu[rid] = vastu_assignments.get(rid, 'C')

                    solver_result = cpsat_solve_layout(
                        plot_width_ft=buildable_width_ft,
                        plot_height_ft=buildable_depth_ft,
                        rooms=internal_rooms,
                        vastu_assignments=floor_vastu,
                        entry_direction=request_data.entry_direction,
                        max_time_seconds=5.0,
                        fixed_positions=fixed_positions, # Enforce stair alignment
                        floor_number=floor_num,
                    )

                    floor_layout = solver_result['rooms']

                    # ── Capture fixed positions from Floor 0 for vertical alignment ─────
                    if floor_num == 0:
                        for r in floor_layout:
                            rtype = r['type'].lower()
                            if rtype in ['staircase', 'lift', 'stairs']:
                                # Normalize to 'staircase' for consistent lookup
                                key = 'staircase' if rtype == 'stairs' else rtype
                                fixed_positions[key] = {
                                    'x': round(r['x'], 2),
                                    'y': round(r['y'], 2),
                                    'width': r['width'],
                                    'height': r['height']
                                }

                    # ── Place External Rooms (Sump, Septic) in Setbacks ──
                    # Place in rear setback (outside structural walls)
                    for i, ext in enumerate(external_rooms):
                        ext_y = buildable_depth_ft + (2.0 if i == 0 else 6.0) # Outside buildable y-range (rear)
                        ext_x = 2.0
                        floor_layout.append({
                            **ext,
                            'id': f"{ext['type']}_{floor_num}",
                            'x': round(ext_x + setback_offset_x_ft, 2),
                            'y': round(ext_y + setback_offset_y_ft, 2),
                            'width': 6.0, 'height': 4.0,
                            'area': 24.0, 'floor': floor_num,
                            'is_external_placed': True,
                            'is_annotation': True
                        })

                    # Apply setback offsets and floor number
                    for room in floor_layout:
                        if not room.get('is_external_placed'):
                            room['x'] = round(room.get('x', 0) + setback_offset_x_ft, 2)
                            room['y'] = round(room.get('y', 0) + setback_offset_y_ft, 2)
                        room['floor'] = floor_num

                    # Validate layout
                    validation = validate_layout(
                        floor_layout, buildable_width_ft, buildable_depth_ft
                    )
                    logger.info(
                        f"Floor {floor_num} solver: status={solver_result['status']}, "
                        f"time={solver_result['solve_time_ms']}ms, "
                        f"coverage={solver_result['coverage_pct']}%, "
                        f"overlaps={validation['overlap_count']}, "
                        f"valid={validation['is_valid']}"
                    )

                    bsp_engine = f"cpsat_{solver_result['status'].lower()}"

                    all_floor_layouts[floor_num] = floor_layout
                    print(f"[CPSAT] Floor {floor_num}: {len(floor_layout)} rooms, "
                          f"status={solver_result['status']}, "
                          f"coverage={solver_result['coverage_pct']}%, "
                          f"overlaps={validation['overlap_count']}")

        # ── PRIMARY PLACED ROOMS = typical floor 1 ──
        placed_rooms = all_floor_layouts.get(1, all_floor_layouts.get(0, []))
        layout_results = {
            'total_area_used': sum(r.get('area', r.get('width', 0) * r.get('height', 0)) for r in placed_rooms),
            'plot_dimensions': [plot_width, plot_depth],
            'staircase': None,
            'rooms': placed_rooms,
        }
        print(f"✅ Multi-floor pipeline: {len(all_floor_layouts)} floors generated")

        # ── DETERMINE PRIMARY LAYOUT ──────────────────────────────────────────
        bsp_rooms = list(placed_rooms)
        # (Voronoi mode removed in v4.0 overhaul)

        # ── FEATURE A: Circulation Engine (typical floor) ─────────────────────
        circulation_data = None
        if request_data.enable_circulation:
            circ_engine = CirculationEngine(plot_width, plot_depth)
            circulation_data = circ_engine.find_optimal_corridors(placed_rooms)
            print(f"🛤️ Circulation: efficiency={circulation_data['efficiency_score']}%, "
                  f"corridors={len(circulation_data['corridors'])}")

        # Final Dedup: Remove duplicate labels (especially multiple ROOFs)
        final_floor_layouts = {}
        final_floor_svgs = {}
        final_labels = {}
        seen_lbls = set()
        
        FLOOR_LABELS = {}
        for fn in all_floor_layouts:
            label = program.get_floor_label(fn)
            FLOOR_LABELS[fn] = label

        # Dedup: if any intermediate floor got "ROOF PLAN", fix it
        for fn in sorted(FLOOR_LABELS.keys()):
            if fn > 0 and fn < roof_floor_num and FLOOR_LABELS[fn] == "ROOF PLAN":
                suffix_map = {1: '1ST', 2: '2ND', 3: '3RD'}
                FLOOR_LABELS[fn] = f"{suffix_map.get(fn, f'{fn}TH')} FLOOR PLAN"

        for fn in sorted(all_floor_layouts.keys()):
            lbl = FLOOR_LABELS.get(fn, f"FLOOR {fn}")
            if lbl in seen_lbls:
                continue
            seen_lbls.add(lbl)
            final_floor_layouts[fn] = all_floor_layouts[fn]
            final_labels[fn] = lbl

        # ── FEATURE E: Structural Analysis (Init engine) ──────────────────────
        struct_engine = StructuralEngine(plot_width, plot_depth)
        structural_data = None

        # ── v3.0: ACCESSIBILITY ENGINE ─────────────────────────────────────────
        updated_doors, accessibility_report = ensure_full_accessibility(
            placed_rooms,
            doors=[],
            entry_direction=request_data.entry_direction
        )

        # ── v3.0: FURNITURE ENGINE ─────────────────────────────────────────────
        furniture_placements = []
        if request_data.include_furniture:
            furniture_placements = FurnitureEngine(placed_rooms, updated_doors)

        # ── PER-FLOOR RENDERING ──
        for fn, floor_rooms_list in final_floor_layouts.items():
            # Compute structural columns per-floor for accuracy
            floor_structural_data = struct_engine.find_column_positions(
                floor_rooms_list, norm_btype, total_floors
            )
            
            # Track principal structural data for top-level response
            if fn == 1 or (fn == 0 and structural_data is None):
                structural_data = floor_structural_data

            try:
                floor_svg = render_blueprint_professional(
                    placement_data=floor_rooms_list,
                    plot_width=plot_width,
                    plot_height=plot_depth,
                    scale=SCALE,
                    floor_label=final_labels.get(fn, f"FLOOR {fn}"),
                    vastu_score=vastu_results,
                    user_tier=request_data.user_tier,
                    original_unit_system=request_data.original_unit_system,
                    heavy_elements=floor_structural_data,
                    building_program=program,
                    floor_number=fn,
                    shape_config=shape_config,
                    style_metadata=style_metadata,
                    furniture_items=furniture_placements if fn >= 1 and fn <= total_floors else [],
                )
                final_floor_svgs[fn] = floor_svg
            except Exception as svg_err:
                print(f"⚠️ SVG render failed for floor {fn}: {svg_err}")
                final_floor_svgs[fn] = ""

        # Primary SVG (use 1st floor if multi-story, else ground)
        if total_floors > 0:
            svg_blueprint = final_floor_svgs.get(1, final_floor_svgs.get(0, ""))
        else:
            svg_blueprint = final_floor_svgs.get(0, "")

        print(f"📐 Renderer: {len(floor_svgs)} floor SVGs generated")

        # ── v3.0: PROPORTION VALIDATOR ─────────────────────────────────────────
        proportion_data = validate_proportions(placed_rooms)
        print(f"📏 Proportions: score={proportion_data['proportion_score']}, "
              f"errors={proportion_data['errors']}, warnings={proportion_data['warnings']}")

        # ── v3.0: BLUEPRINT SCORER ─────────────────────────────────────────────
        blueprint_score = score_blueprint(
            placed_rooms, plot_width, plot_depth,
            vastu_score=vastu_results,
            accessibility_report=accessibility_report,
            proportion_report=proportion_data,
        )
        print(f"🏆 Blueprint Score: {blueprint_score['overall']}/100 ({blueprint_score['grade']})"
              f" — {blueprint_score['label']}")

        # ── v3.0: SOLAR & WIND ANALYSIS ────────────────────────────────────────
        environment_data = {}
        try:
            environment_data = analyze_environment(
                placed_rooms, plot_width, plot_depth,
                latitude=request_data.latitude
            )
            print(f"☀️ Environment: Sun={environment_data['overall_sun_score']}, "
                  f"Vent={environment_data['overall_vent_score']}")
        except Exception as env_err:
            print(f"⚠️ Environment analysis skipped: {env_err}")

        # ── v3.0: ISOMETRIC 3D PREVIEW ─────────────────────────────────────────
        try:
            iso_svg = render_isometric(
                placed_rooms, plot_width, plot_depth,
                style=active_style if active_style else "residential"
            )
            print(f"🏠 Isometric 3D: {len(iso_svg)} chars")
        except Exception as iso_err:
            print(f"⚠️ Isometric render skipped: {iso_err}")
            iso_svg = None

        # ── FEATURE D: Refinement Diff ────────────────────────────────────────
        diff_result = None
        if request_data.previous_layout:
            diff = compute_diff(request_data.previous_layout, placed_rooms)
            diff_result = diff.to_dict()
            print(f"🔀 Diff: {diff_result['total_changes']} changes — {diff_result['summary']}")

        # ── RESPONSE ──────────────────────────────────────────────────────────
        response_data = {
            "svg": svg_blueprint,
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

            # Multi-floor layouts & SVGs
            "floor_svgs": {str(fn): svg for fn, svg in final_floor_svgs.items()},
            "floor_labels": {str(fn): lbl for fn, lbl in final_labels.items()},
            "all_floor_layouts": {
                str(fn): rooms for fn, rooms in final_floor_layouts.items()
            },

            # Feature A
            "circulation": circulation_data,

            # Feature B
            "vastu_heatmap": vastu_heatmap_data,
            "room_vastu_scores": room_scores,

            # Feature C
            "architectural_style": style_metadata,

            # Feature D
            "layout_diff": diff_result,
            "current_layout": placed_rooms,

            # Feature E
            "structural": structural_data,

            # Site Context (setbacks & buildable envelope)
            # SANITIZATION: Remove non-serializable Shapely Polygon objects
            "site_context": {k: v for k, v in site_context.items() if k != 'buildable_polygon'},

            # v3.0 Feature I: Blueprint Score
            "blueprint_score": blueprint_score,

            # v3.0 Feature J: Solar & Wind
            "environment": environment_data,

            # v3.0 Feature K: Isometric 3D
            "isometric_svg": iso_svg,

            # v3.0 Feature G: Room Proportions
            "proportions": proportion_data,

            # v3.0 Feature F: Accessibility
            "accessibility_report": accessibility_report,

            # v3.0 Feature: Alternative Layout
            "alternative_svg": alternative_svg,
        }

        # Auto-save project for history/gallery
        try:
            project_id = await save_project({
                "prompt": request_data.prompt,
                "svg": svg_blueprint,
                "scores": {
                    "vastu": vastu_results["score"],
                    "blueprint_overall": blueprint_score["overall"]
                }
            })
            response_data["project_id"] = project_id
            print(f"💾 Auto-saved project: {project_id}")
        except Exception as save_err:
            logger.warning(f"Failed to auto-save project: {save_err}")

        return {"success": True, "data": response_data, "error": None}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Generation error: {e}")
        logger.error(f"Blueprint generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pass


# ── UTILITY ENDPOINTS ─────────────────────────────────────────────────────────

@router.get("/styles")
async def list_styles():
    """Returns all available architectural style presets."""
    return {"success": True, "data": get_all_style_names()}
