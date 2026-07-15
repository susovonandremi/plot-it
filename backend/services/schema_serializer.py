# backend/services/schema_serializer.py
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from shapely.geometry import box as shapely_box
from shapely.ops import unary_union

from services.constants import WALL_ADJACENCY_TOL

from models.geometry import (
    Orientation, WallType, Vec2, BBox, WallSegment, DoorPlacement, WindowPlacement, Room,
    normalize_room_type
)
from services.geometry_processor import (
    get_plot_bounds,
    extract_wall_segments,
    find_door_positions,
    find_window_positions,
    apply_openings_to_walls,
)

# ── PYDANTIC MODELS FOR APIS ──

class Metadata(BaseModel):
    generated_at: str
    solver: str
    solver_time_ms: int
    plot_width_ft: float
    plot_height_ft: float
    plot_area_sqft: float
    building_type: str
    floor_number: int
    floor_label: str
    vastu_score: Dict[str, Any]
    shape_config: Dict[str, Any]
    unit_system: str

class SchemaRoom(BaseModel):
    id: str
    type: str
    label: str
    x: float
    y: float
    width: float
    height: float
    area_sqft: float
    vastu_zone: str
    floor_material: str
    is_annotation: bool = False

class WallSegmentSchema(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    orientation: str
    is_exterior: bool
    adjacent_room_ids: List[str]
    has_opening: bool

class Walls(BaseModel):
    boundary_polygon_wkt: str
    exterior_thickness_ft: float
    interior_thickness_ft: float
    segments: List[WallSegmentSchema]

class SchemaDoor(BaseModel):
    id: str
    room1_id: str
    room2_id: str
    door_type: str
    width_ft: float
    position: Dict[str, float]
    orientation: str
    swing_direction: str
    wall_segment_id: str

class SchemaWindow(BaseModel):
    id: str
    room_id: str
    window_type: str
    width_ft: float
    position: Dict[str, float]
    orientation: str
    side: str
    wall_segment_id: str

class SchemaFixture(BaseModel):
    id: str
    room_id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    rotation_deg: float
    anchor_wall: str

class SchemaFurniture(BaseModel):
    id: str
    room_id: str
    type: str
    label: str
    x: float
    y: float
    width: float
    height: float
    rotation_deg: float
    symbol: str

class SchemaColumn(BaseModel):
    id: str
    cx: float
    cy: float
    width: float
    height: float
    reason: str

class SchemaBeam(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    type: str
    length_ft: float

class Structural(BaseModel):
    columns: List[SchemaColumn]
    beams: List[SchemaBeam]

class SiteContext(BaseModel):
    setback_ft: float
    entry_side: str
    road_side: str
    entry_room_id: str

class DimensionSegment(BaseModel):
    start_ft: float
    end_ft: float
    label: str

class DimensionChain(BaseModel):
    value_ft: float
    label: str

class DimensionChains(BaseModel):
    top_facade: List[DimensionSegment]
    left_facade: List[DimensionSegment]
    overall_width: DimensionChain
    overall_depth: DimensionChain

class FloorPlanSchema(BaseModel):
    version: str = "1.0.0"
    metadata: Metadata
    rooms: List[SchemaRoom]
    walls: Walls
    doors: List[SchemaDoor]
    windows: List[SchemaWindow]
    fixtures: List[SchemaFixture] = []
    furniture: List[SchemaFurniture] = []
    structural: Structural
    site_context: SiteContext
    dimension_chains: DimensionChains


# ── SERIALIZATION LOGIC ──

def _format_dimension_str(value_ft: float) -> str:
    """Format dimension to 11'-6\" format."""
    total_inches = round(value_ft * 12)
    ft = total_inches // 12
    inches = total_inches % 12
    return f"{int(ft)}'-{int(inches):02d}\""

def serialize_floor_plan(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    vastu_score: Dict[str, Any],
    building_program: Optional[Any] = None,
    floor_number: int = 0,
    shape_config: Optional[Dict[str, Any]] = None,
    heavy_elements: Optional[Dict[str, Any]] = None,
    furniture_items: Optional[List[Dict[str, Any]]] = None,
    unit_system: str = "imperial",
    solver_time_ms: int = 0
) -> Dict[str, Any]:
    """
    Pure-data serializer that compiles layout info into a structured JSON Schema.
    """
    if not placed_rooms:
        return {}

    # Shift all rooms relative to top-left to start at (0,0) internally
    min_x = min(r['x'] for r in placed_rooms)
    min_y = min(r['y'] for r in placed_rooms)
    
    shifted_rooms = []
    for r in placed_rooms:
        sr = dict(r)
        sr['x'] = round(r['x'] - min_x, 4)
        sr['y'] = round(r['y'] - min_y, 4)
        shifted_rooms.append(sr)

    plan_width_ft = max(r['x'] + r['width'] for r in shifted_rooms)
    plan_height_ft = max(r['y'] + r['height'] for r in shifted_rooms)

    # 1. Metadata
    floor_names = ["GROUND FLOOR PLAN", "FIRST FLOOR PLAN", "SECOND FLOOR PLAN", "THIRD FLOOR PLAN", "FOURTH FLOOR PLAN"]
    floor_label = floor_names[floor_number] if floor_number < len(floor_names) else f"FLOOR {floor_number} PLAN"
    if building_program and hasattr(building_program, 'get_floor_label'):
        floor_label = building_program.get_floor_label(floor_number)

    building_type = "independent_house"
    if building_program and hasattr(building_program, 'get_metadata'):
        building_type = building_program.get_metadata().get('building_type', 'independent_house')

    metadata = Metadata(
        generated_at=datetime.utcnow().isoformat() + "Z",
        solver="cp_sat_v2",
        solver_time_ms=solver_time_ms,
        plot_width_ft=plot_width,
        plot_height_ft=plot_height,
        plot_area_sqft=plot_width * plot_height,
        building_type=building_type,
        floor_number=floor_number,
        floor_label=floor_label,
        vastu_score=vastu_score,
        shape_config=shape_config or {"type": "rectangle"},
        unit_system=unit_system
    )

    # 2. Rooms
    rooms_list = []
    ROOM_FLOOR_MATERIALS = {
        'living': 'marble', 'dining': 'marble', 'bedroom': 'hardwood',
        'master_bedroom': 'hardwood', 'bathroom': 'tile', 'kitchen': 'tile',
        'pooja': 'marble', 'study': 'hardwood', 'verandah': 'terracotta',
        'balcony': 'terracotta', 'courtyard': 'terracotta', 'entrance': 'marble',
        'foyer': 'marble', 'passage': 'concrete', 'staircase': 'concrete',
    }
    for r in shifted_rooms:
        rtype = normalize_room_type(r['type'])
        mat = ROOM_FLOOR_MATERIALS.get(rtype, "concrete")
        
        rooms_list.append(SchemaRoom(
            id=r['id'],
            type=rtype,
            label=r.get('label', r.get('type', 'ROOM')).upper(),
            x=r['x'],
            y=r['y'],
            width=r['width'],
            height=r['height'],
            area_sqft=r['width'] * r['height'],
            vastu_zone=r.get('zone', r.get('vastu_zone', 'unknown')),
            floor_material=mat,
            is_annotation=False
        ))

    # 3. Resolve doors, windows, and walls
    plot_bounds = {'min_x': 0.0, 'min_y': 0.0, 'max_x': plan_width_ft, 'max_y': plan_height_ft}
    wall_segments = extract_wall_segments(shifted_rooms, plot_bounds, shape_config)
    doors = find_door_positions(shifted_rooms, building_program)
    
    # Accessibility Engine (BFS resolution)
    try:
        from services.accessibility_engine import ensure_full_accessibility
        entry_dir = getattr(building_program, 'entry_direction', 'N') or 'N'
        doors, _ = ensure_full_accessibility(shifted_rooms, doors, entry_dir)
    except Exception:
        pass

    windows = find_window_positions(shifted_rooms, plot_bounds, building_program)
    
    # Tag orientations
    for w in wall_segments['horizontal']:
        w['orientation'] = 'horizontal'
    for w in wall_segments['vertical']:
        w['orientation'] = 'vertical'
    wall_segments['all'] = wall_segments['horizontal'] + wall_segments['vertical']

    broken_walls = apply_openings_to_walls(wall_segments, doors, windows)
    
    for w in broken_walls['horizontal']:
        w['orientation'] = 'horizontal'
    for w in broken_walls['vertical']:
        w['orientation'] = 'vertical'
    broken_walls['all'] = broken_walls['horizontal'] + broken_walls['vertical']

    # Helper function to find matching wall segment
    def find_wall_id(pos_x, pos_y, orientation):
        TOL = WALL_ADJACENCY_TOL
        for w in wall_segments['all']:
            if w['orientation'] == orientation:
                if orientation == 'vertical':
                    if abs(w['x1'] - pos_x) < TOL and w['y1'] - TOL <= pos_y <= w['y2'] + TOL:
                        return f"wall_v_{round(w['x1'], 2)}_{round(w['y1'], 2)}"
                else:
                    if abs(w['y1'] - pos_y) < TOL and w['x1'] - TOL <= pos_x <= w['x2'] + TOL:
                        return f"wall_h_{round(w['x1'], 2)}_{round(w['y1'], 2)}"
        return "unknown"

    # Wall boundary polygon WKT
    # Run the Shapely wall boundary builder
    from services.geometry_processor import _build_wall_boundary
    boundary_poly = _build_wall_boundary(shifted_rooms, plan_width_ft, plan_height_ft)
    
    # Subtract doors (doorways) from wall boundary polygon to leave blank spaces
    from shapely.geometry import box as shapely_box
    wall_poly = boundary_poly.polygon
    for d in doors:
        dx, dy = d['position']['x'], d['position']['y']
        dw = d['width']
        if d['orientation'] == 'vertical':
            # Cut vertical gap (use 1.5 ft thick cutout to ensure wall slice)
            cutout = shapely_box(dx - 0.75, dy - dw/2.0, dx + 0.75, dy + dw/2.0)
        else:
            # Cut horizontal gap
            cutout = shapely_box(dx - dw/2.0, dy - 0.75, dx + dw/2.0, dy + 0.75)
        wall_poly = wall_poly.difference(cutout)
        
    boundary_wkt = wall_poly.wkt if hasattr(wall_poly, 'wkt') else ""

    wall_schemas = []
    for w in broken_walls['all']:
        wall_id = f"wall_{'h' if w['orientation'] == 'horizontal' else 'v'}_{round(w['x1'], 2)}_{round(w['y1'], 2)}"
        # Check if wall has opening
        has_op = False
        for d in doors:
            if d['orientation'] == w['orientation']:
                if w['orientation'] == 'vertical' and abs(w['x1'] - d['position']['x']) < 0.2 and w['y1'] <= d['position']['y'] <= w['y2']:
                    has_op = True
        for win in windows:
            if win['orientation'] == w['orientation']:
                if w['orientation'] == 'vertical' and abs(w['x1'] - win['position']['x']) < 0.2 and w['y1'] <= win['position']['y'] <= w['y2']:
                    has_op = True

        wall_schemas.append(WallSegmentSchema(
            id=wall_id,
            x1=w['x1'], y1=w['y1'], x2=w['x2'], y2=w['y2'],
            orientation=w['orientation'],
            is_exterior=w.get('is_exterior', False),
            adjacent_room_ids=w.get('room_ids', []),
            has_opening=has_op
        ))

    walls = Walls(
        boundary_polygon_wkt=boundary_wkt,
        exterior_thickness_ft=0.75,
        interior_thickness_ft=0.5,
        segments=wall_schemas
    )

    # Doors Schema
    doors_schema = []
    for idx, d in enumerate(doors):
        d_id = f"door_{idx+1:03d}"
        doors_schema.append(SchemaDoor(
            id=d_id,
            room1_id=d['room1_id'],
            room2_id=d['room2_id'],
            door_type=d['door_type'],
            width_ft=d['width'],
            position={'x': d['position']['x'], 'y': d['position']['y']},
            orientation=d['orientation'],
            swing_direction="into_room1", # default swing
            wall_segment_id=find_wall_id(d['position']['x'], d['position']['y'], d['orientation'])
        ))

    # Windows Schema
    windows_schema = []
    for idx, win in enumerate(windows):
        w_id = f"win_{idx+1:03d}"
        windows_schema.append(SchemaWindow(
            id=w_id,
            room_id=win['room_id'],
            window_type=win['window_type'],
            width_ft=win['width'],
            position={'x': win['position']['x'], 'y': win['position']['y']},
            orientation=win['orientation'],
            side=win['side'],
            wall_segment_id=find_wall_id(win['position']['x'], win['position']['y'], win['orientation'])
        ))

    # 4. Bathroom and Kitchen Fixtures
    from services.fixture_placer import FixturePlacer
    placer = FixturePlacer()
    fixtures_schema = []
    for r in shifted_rooms:
        room_fixtures = placer.place_in_room(r, doors)
        for fix in room_fixtures:
            fixtures_schema.append(SchemaFixture(
                id=fix.id,
                room_id=fix.room_id,
                type=fix.type,
                x=fix.x,
                y=fix.y,
                width=fix.width,
                height=fix.height,
                rotation_deg=fix.rotation_deg,
                anchor_wall=fix.anchor_wall
            ))

    # 5. Placed Furniture
    furniture_schema = []
    if furniture_items:
        for idx, f in enumerate(furniture_items):
            # The input furniture coordinate is already absolute, but let's shift it as well
            fx_shifted = round(f['x'] - min_x, 2)
            fy_shifted = round(f['y'] - min_y, 2)
            f_id = f"furn_{idx+1:03d}"
            
            furniture_schema.append(SchemaFurniture(
                id=f_id,
                room_id=f['room_id'],
                type=f['type'],
                label=f['label'],
                x=fx_shifted,
                y=fy_shifted,
                width=f['width'],
                height=f['height'],
                rotation_deg=float(f.get('rotation', 0)),
                symbol=f['symbol']
            ))

    # 6. Structural columns & beams
    columns_schema = []
    beams_schema = []
    if heavy_elements:
        cols = heavy_elements.get('columns', [])
        for idx, col in enumerate(cols):
            cx_shifted = round(col['cx'] - min_x, 2) if 'cx' in col else round(col['x'] - min_x + col['width']/2, 2)
            cy_shifted = round(col['cy'] - min_y, 2) if 'cy' in col else round(col['y'] - min_y + col['height']/2, 2)
            columns_schema.append(SchemaColumn(
                id=f"col_{idx+1:03d}",
                cx=cx_shifted,
                cy=cy_shifted,
                width=col.get('width', 0.75),
                height=col.get('height', 1.0),
                reason=col.get('reason', 'grid')
            ))
        
        beams = heavy_elements.get('beams', [])
        for idx, b in enumerate(beams):
            beams_schema.append(SchemaBeam(
                id=f"beam_{idx+1:03d}",
                x1=round(b['x1'] - min_x, 2),
                y1=round(b['y1'] - min_y, 2),
                x2=round(b['x2'] - min_x, 2),
                y2=round(b['y2'] - min_y, 2),
                type=b.get('beam_type', 'primary'),
                length_ft=b.get('length_ft', 0.0)
            ))

    structural = Structural(columns=columns_schema, beams=beams_schema)

    # 7. Site Context
    # Find entrance room
    entrance_room = next((r for r in shifted_rooms if normalize_room_type(r['type']) in ['entrance', 'foyer', 'entry']), None)
    entry_room_id = entrance_room['id'] if entrance_room else "unknown"

    entry_dir = "bottom"
    if building_program and hasattr(building_program, 'entry_direction'):
        direction_map = {'N': 'top', 'S': 'bottom', 'E': 'right', 'W': 'left'}
        entry_dir = direction_map.get(building_program.entry_direction, 'bottom')

    site_context = SiteContext(
        setback_ft=5.0,
        entry_side=entry_dir,
        road_side=entry_dir,
        entry_room_id=entry_room_id
    )

    # 8. Dimension Chains
    # Find rooms on top boundary (y=0)
    top_rooms = sorted(
        [r for r in shifted_rooms if abs(r['y']) < 0.1],
        key=lambda r: r['x']
    )
    top_segments = [
        DimensionSegment(
            start_ft=r['x'],
            end_ft=r['x'] + r['width'],
            label=_format_dimension_str(r['width'])
        ) for r in top_rooms
    ]

    # Find rooms on left boundary (x=0)
    left_rooms = sorted(
        [r for r in shifted_rooms if abs(r['x']) < 0.1],
        key=lambda r: r['y']
    )
    left_segments = [
        DimensionSegment(
            start_ft=r['y'],
            end_ft=r['y'] + r['height'],
            label=_format_dimension_str(r['height'])
        ) for r in left_rooms
    ]

    dimension_chains = DimensionChains(
        top_facade=top_segments,
        left_facade=left_segments,
        overall_width=DimensionChain(value_ft=plan_width_ft, label=_format_dimension_str(plan_width_ft)),
        overall_depth=DimensionChain(value_ft=plan_height_ft, label=_format_dimension_str(plan_height_ft))
    )

    # Compile the final schema
    floor_plan_schema = FloorPlanSchema(
        metadata=metadata,
        rooms=rooms_list,
        walls=walls,
        doors=doors_schema,
        windows=windows_schema,
        fixtures=fixtures_schema,
        furniture=furniture_schema,
        structural=structural,
        site_context=site_context,
        dimension_chains=dimension_chains
    )

    return floor_plan_schema.model_dump()
