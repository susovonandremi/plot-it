"""
WebSocket Streaming Route — Feature D: Real-Time Blueprint Generation
======================================================================
Provides a WebSocket endpoint that streams generation progress events
to the frontend in real-time.

Event format (JSON):
  {"event": "stage", "data": {"stage": "vastu", "progress": 30, "message": "Optimizing Vastu zones..."}}
  {"event": "complete", "data": {"svg": "...", "vastu_score": 85, ...}}
  {"event": "error", "data": {"message": "..."}}

Stages and progress:
  parsing        →  5%
  building_prog  → 20%
  vastu          → 35%
  circulation    → 50%
  layout         → 65%
  structural     → 75%
  rendering      → 90%
  complete       → 100%
"""

import math
import json
import logging
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional

from services.vastu_engine import assign_vastu_zones, calculate_vastu_score
from services.vastu_heatmap import calculate_room_vastu_scores, apply_vastu_resizing, generate_vastu_heatmap
from services.professional_svg_renderer import render_blueprint_professional
from services.building_program import BuildingProgram, create_building_program
from services.circulation_engine import CirculationEngine
from services.structural_engine import StructuralEngine
from services.style_engine import detect_style, apply_style_constraints

from services.proportion_validator import validate_proportions
from services.blueprint_scorer import score_blueprint
from services.solar_wind_engine import analyze_environment
from services.isometric_renderer import render_isometric
from services.accessibility_engine import ensure_full_accessibility
from services.site_context_engine import SiteContextEngine
from services.furniture_engine import place_furniture as FurnitureEngine

# v4.0: CP-SAT Constraint Solver
from services.constraint_solver import solve_layout as cpsat_solve_layout
from services.geometric_validator import validate_layout

logger = logging.getLogger("plotai.stream")
router = APIRouter()


async def _emit(ws: WebSocket, event: str, data: Dict[str, Any]):
    """Helper to send a JSON event over WebSocket."""
    await ws.send_text(json.dumps({"event": event, "data": data}))


@router.websocket("/generate")
async def stream_generate(ws: WebSocket):
    """
    WebSocket endpoint for streaming blueprint generation.

    Client sends a JSON payload identical to the POST /generate body.
    Server streams progress events and finally sends the complete blueprint.

    Usage (JavaScript):
        const ws = new WebSocket("ws://localhost:8000/api/v1/stream/generate");
        ws.onopen = () => ws.send(JSON.stringify({ plot_size_sqft: 1200, rooms: [...] }));
        ws.onmessage = (e) => {
            const { event, data } = JSON.parse(e.data);
            if (event === "stage") updateProgress(data.progress, data.message);
            if (event === "complete") renderBlueprint(data.svg);
            if (event === "error") showError(data.message);
        };
    """
    await ws.accept()
    logger.info("WebSocket connection accepted")

    try:
        pass
        # Receive the generation request payload
        raw = await ws.receive_text()
        request_data = json.loads(raw)

        # ── STAGE 1: Parsing & Validation ──────────────────────────────────
        await _emit(ws, "stage", {
            "stage": "parsing",
            "progress": 5,
            "message": "Parsing architectural requirements..."
        })

        plot_size_sqft = float(request_data.get("plot_size_sqft") or 1200)
        total_floors = int(request_data.get("floors") or 1)
        raw_rooms = request_data.get("rooms", [])
        user_tier = request_data.get("user_tier", "free")
        building_type = request_data.get("building_type", "independent_house")
        entry_direction = request_data.get("entry_direction", "N")
        has_lift = request_data.get("has_lift", False)
        has_balcony = request_data.get("has_balcony", False)
        has_verandah = request_data.get("has_verandah", False)
        plot_width_ft = request_data.get("plot_width_ft")
        plot_depth_ft = request_data.get("plot_depth_ft")
        original_unit_system = request_data.get("original_unit_system")
        architectural_style = request_data.get("architectural_style")
        previous_layout = request_data.get("previous_layout")
        style_meta = None

        plot_side = round(math.sqrt(plot_size_sqft), 1)
        plot_width = plot_width_ft or plot_side
        plot_depth = plot_depth_ft or plot_side
        # ── EXTRACTION: Dimensions & Entry ────────────────────────────────
        prompt_text = request_data.get("prompt", "")
        dim_match = re.search(r"(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)", prompt_text)
        if dim_match:
             w_val = float(dim_match.group(1))
             d_val = float(dim_match.group(2))
             if abs(w_val * d_val - plot_size_sqft) < 10:
                  plot_width = w_val
                  plot_depth = d_val

        if entry_direction == "N":
             p_lower = prompt_text.lower()
             if "entry south" in p_lower or "facing south" in p_lower: entry_direction = "S"
             elif "entry east" in p_lower or "facing east" in p_lower: entry_direction = "E"
             elif "entry west" in p_lower or "facing west" in p_lower: entry_direction = "W"

        # Apply style constraints if detected
        if architectural_style:
            raw_rooms, style_meta = apply_style_constraints(raw_rooms, architectural_style, plot_size_sqft)
            await _emit(ws, "stage", {
                "stage": "style",
                "progress": 10,
                "message": f"Applying {style_meta['display_name']} style constraints..."
            })

        # ── STAGE 2: Building Program ───────────────────────────────────────
        await _emit(ws, "stage", {
            "stage": "building_program",
            "progress": 20,
            "message": "Enriching room program with mandatory elements..."
        })

        program = create_building_program(
            plot_area=plot_size_sqft,
            user_rooms=raw_rooms,
            building_type=building_type,
            floor_number=0,
            floors_total=total_floors,
            entry_direction=entry_direction,
            has_lift=has_lift,
            has_balcony=has_balcony,
            has_verandah=has_verandah,
            plot_width=plot_width,
            plot_depth=plot_depth,
        )
        # enriched_rooms (residential core list) for Vastu analysis
        # For 1-story: Floor 0 has everything. For Multi-story: Floor 1 is core.
        core_fn = 1 if total_floors > 1 else 0
        res_rooms = program.get_floor_program(core_fn, total_floors)
        vastu_assignments = assign_vastu_zones(res_rooms)
        vastu_results = calculate_vastu_score(vastu_assignments)

        # ── STAGE 3: Site Context ───────────────────────────────────────────
        await _emit(ws, "stage", {
            "stage": "site_context",
            "progress": 30,
            "message": "Calculating setbacks and buildable envelope..."
        })
        FT_TO_M = 0.3048
        M_TO_FT = 3.28084
        site_engine = SiteContextEngine()
        site_context = site_engine.calculate_buildable_envelope(
            plot_width_m=plot_width * FT_TO_M,
            plot_depth_m=plot_depth * FT_TO_M,
            building_type=building_type,
            entry_direction=entry_direction,
        )
        bw_ft = round(site_context['buildable_width'] * M_TO_FT, 2)
        bd_ft = round(site_context['buildable_depth'] * M_TO_FT, 2)
        ox_ft = round(site_context['buildable_x'] * M_TO_FT, 2)
        oy_ft = round(site_context['buildable_y'] * M_TO_FT, 2)

        # ── STAGE 4: Multi-floor Layout Generation ──────────────────────────
        await _emit(ws, "stage", {
            "stage": "layout",
            "progress": 50,
            "message": "Generating all floor plans..."
        })
        
        all_floor_layouts = {}
        floor_svgs = {}
        FLOOR_LABELS = {}
        placed_rooms = []
        
        roof_floor_num = total_floors + 1

        for fn in range(total_floors + 2):
            floor_rooms = program.get_floor_program(fn, total_floors)
            FLOOR_LABELS[fn] = program.get_floor_label(fn)
            
            # 1-story house: Ground floor needs residential rooms via BSP
            # Multi-story house: Ground floor is usually stilt/parking with fixed layout
            if fn == 0 and total_floors > 1:
                from services.building_program import generate_ground_floor_layout
                layout = generate_ground_floor_layout(bw_ft, bd_ft, has_lift=has_lift)
                for r in layout:
                    r['x'] = round(r.get('x', 0) + ox_ft, 2)
                    r['y'] = round(r.get('y', 0) + oy_ft, 2)
                all_floor_layouts[fn] = layout
            elif fn == roof_floor_num:
                from services.building_program import generate_roof_floor_layout
                layout = generate_roof_floor_layout(bw_ft, bd_ft, has_lift=has_lift, roof_floor_num=roof_floor_num)
                for r in layout:
                    r['x'] = round(r.get('x', 0) + ox_ft, 2)
                    r['y'] = round(r.get('y', 0) + oy_ft, 2)
                all_floor_layouts[fn] = layout
            else:
                if fn > 1 and 1 in all_floor_layouts:
                    import copy
                    layout = copy.deepcopy(all_floor_layouts[1])
                    for r in layout: r['floor'] = fn
                    all_floor_layouts[fn] = layout
                else:
                    # ── CP-SAT CONSTRAINT SOLVER (v4.0) ──────────────────────
                    floor_vastu = {}
                    for room in floor_rooms:
                        rid = room.get('id', '')
                        if rid:
                            floor_vastu[rid] = vastu_assignments.get(rid, 'C')

                    solver_result = cpsat_solve_layout(
                        plot_width_ft=bw_ft,
                        plot_height_ft=bd_ft,
                        rooms=floor_rooms,
                        vastu_assignments=floor_vastu,
                        entry_direction=entry_direction,
                        max_time_seconds=5.0,
                        floor_number=fn,
                    )

                    layout = solver_result['rooms']
                    for r in layout:
                        r['x'] = round(r.get('x', 0) + ox_ft, 2)
                        r['y'] = round(r.get('y', 0) + oy_ft, 2)
                        r['floor'] = fn

                    # Validate layout
                    validation = validate_layout(layout, bw_ft, bd_ft)
                    logger.info(f"Floor {fn} solver: status={solver_result['status']}, valid={validation['is_valid']}")

                    # Primary rooms for downstream tools
                    placed_rooms = list(layout)
                    all_floor_layouts[fn] = layout

        if not placed_rooms and 0 in all_floor_layouts:
            placed_rooms = all_floor_layouts[0]

        # ── STAGE 5: Analysis (Circulation, Structural, Scores) ─────────────
        await _emit(ws, "stage", {
            "stage": "analysis",
            "progress": 75,
            "message": "Analyzing architectural performance..."
        })
        
        circ_engine = CirculationEngine(plot_width, plot_depth)
        circulation_data = circ_engine.find_optimal_corridors(placed_rooms)
        
        struct_engine = StructuralEngine(plot_width, plot_depth)
        structural_data = struct_engine.analyze(placed_rooms)

        # Accessibility & Furniture
        updated_doors, accessibility_report = ensure_full_accessibility(placed_rooms, doors=[], entry_direction=entry_direction)
        furniture_placements = FurnitureEngine(placed_rooms, updated_doors)

        # Vastu Heatmap
        room_scores = calculate_room_vastu_scores(placed_rooms, vastu_assignments)
        placed_rooms_scored = apply_vastu_resizing(placed_rooms, room_scores, plot_size_sqft)
        vastu_heatmap = generate_vastu_heatmap(placed_rooms_scored, room_scores, plot_width=plot_width, plot_height=plot_depth)

        # Scorer & Others
        proportion_data = validate_proportions(placed_rooms)
        blueprint_score = score_blueprint(placed_rooms, plot_width, plot_depth, vastu_score=vastu_results, accessibility_report=accessibility_report, proportion_report=proportion_data)
        
        iso_svg = None
        try:
            iso_svg = render_isometric(placed_rooms, plot_width, plot_depth, style=style_meta['type'] if style_meta else "residential")
        except: pass
        
        environment_data = {}
        try: environment_data = analyze_environment(placed_rooms, plot_width, plot_depth, latitude=float(request_data.get("latitude", 12.0)))
        except: pass

        # ── STAGE 6: Rendering SVGs ─────────────────────────────────────────
        await _emit(ws, "stage", {
            "stage": "rendering",
            "progress": 90,
            "message": "Rendering professional blueprints for all floors..."
        })
        
        for fn, layout in all_floor_layouts.items():
            floor_svgs[fn] = render_blueprint_professional(
                placement_data=layout,
                plot_width=plot_width,
                plot_height=plot_depth,
                vastu_score=vastu_results,
                user_tier=user_tier,
                original_unit_system=original_unit_system,
                building_program=program,
                floor_number=fn,
                furniture_items=furniture_placements if fn >= 1 and fn <= total_floors else [],
                shape_config={"type": "rectangle", "width": bw_ft, "depth": bd_ft},
            )

        # ── STAGE 7: Complete ───────────────────────────────────────────────
        await _emit(ws, "complete", {
            "svg": floor_svgs.get(1, floor_svgs.get(0, "")),
            "floor_svgs": floor_svgs,
            "floor_labels": FLOOR_LABELS,
            "all_floor_layouts": all_floor_layouts,
            "vastu_score": vastu_results["score"],
            "vastu_label": vastu_results["label"],
            "vastu_color": vastu_results["color"],
            "vastu_heatmap": vastu_heatmap,
            "dimensions": (plot_width, plot_depth),
            "engine": "cpsat_stream_v4",
            "floor_label": program.get_floor_label(1 if total_floors > 0 else 0),
            "building_type": building_type,
            "circulation": circulation_data,
            "structural": structural_data,
            "blueprint_score": blueprint_score,
            "environment": environment_data,
            "isometric_svg": iso_svg,
            "proportions": proportion_data,
            "accessibility_report": accessibility_report,
            "current_layout": placed_rooms,
        })

        logger.info(f"WebSocket generation complete: {plot_size_sqft} sqft, {len(placed_rooms)} rooms")

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except json.JSONDecodeError as e:
        await _emit(ws, "error", {"message": f"Invalid JSON payload: {str(e)}"})
    except Exception as e:
        logger.error(f"WebSocket generation error: {e}", exc_info=True)
        try:
            await _emit(ws, "error", {"message": str(e)})
        except Exception:
            pass
    finally:
        pass
        try:
            await ws.close()
        except Exception:
            pass
