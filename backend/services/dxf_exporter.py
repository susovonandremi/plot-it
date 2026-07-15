# backend/services/dxf_exporter.py
import re
from typing import Dict, Any

class DxfWriter:
    def __init__(self):
        self.lines = []

    def section_start(self, name: str):
        self.lines.extend(["0", "SECTION", "2", name])

    def section_end(self):
        self.lines.extend(["0", "ENDSEC"])

    def write_line(self, x1: float, y1: float, x2: float, y2: float, layer: str = "0"):
        self.lines.extend([
            "0", "LINE",
            "8", layer,
            "10", f"{round(x1, 3)}",
            "20", f"{round(y1, 3)}",
            "30", "0.0",
            "11", f"{round(x2, 3)}",
            "21", f"{round(y2, 3)}",
            "31", "0.0"
        ])

    def write_text(self, text: str, x: float, y: float, height: float = 0.5, layer: str = "0", rotation: float = 0.0):
        # DXF text group codes: 1 is content, 40 is height, 50 is rotation angle (deg)
        self.lines.extend([
            "0", "TEXT",
            "8", layer,
            "10", f"{round(x, 3)}",
            "20", f"{round(y, 3)}",
            "30", "0.0",
            "40", f"{round(height, 3)}",
            "1", text,
            "50", f"{round(rotation, 3)}"
        ])

    def write_polyline(self, points: list, layer: str = "0", closed: bool = True):
        self.lines.extend([
            "0", "LWPOLYLINE",
            "8", layer,
            "90", f"{len(points)}",
            "70", "1" if closed else "0",
            "38", "0.0"
        ])
        for pt in points:
            self.lines.extend([
                "10", f"{round(pt[0], 3)}",
                "20", f"{round(pt[1], 3)}"
            ])

    def get_dxf_string(self) -> str:
        return "\n".join(self.lines + ["0", "EOF", ""])


def parse_wkt_points(wkt: str) -> list:
    """Parses WKT POLYGON coordinates into list of rings with points."""
    if not wkt:
        return []
    
    # Extract coordinates between parentheses
    rings_raw = re.findall(r"\([^()]*\)", wkt)
    rings = []
    for r in rings_raw:
        pts_raw = r.replace("(", "").replace(")", "").split(",")
        ring_pts = []
        for pt in pts_raw:
            parts = pt.strip().split()
            if len(parts) == 2:
                ring_pts.append((float(parts[0]), float(parts[1])))
        if ring_pts:
            rings.append(ring_pts)
    return rings


def export_to_dxf(schema: Dict[str, Any]) -> str:
    """
    Zero-dependency exporter that translates a FloorPlanSchema JSON object
    into standard ASCII DXF format.
    """
    writer = DxfWriter()
    writer.section_start("ENTITIES")

    # 1. Rooms
    rooms = schema.get("rooms", [])
    for room in rooms:
        x, y = room["x"], room["y"]
        w, h = room["width"], room["height"]
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        writer.write_polyline(pts, layer="ROOMS", closed=True)

        # Label Text (centered in the room)
        cx = x + w / 2
        cy = y + h / 2
        writer.write_text(room["label"], cx - 1.0, cy + 0.2, height=0.4, layer="ROOM_LABELS")
        dim_str = f"{round(w, 1)}x{round(h, 1)}"
        writer.write_text(dim_str, cx - 0.7, cy - 0.4, height=0.3, layer="ROOM_LABELS")

    # 2. Walls
    walls = schema.get("walls", {})
    wkt = walls.get("boundary_polygon_wkt", "")
    rings = parse_wkt_points(wkt)
    for ring in rings:
        writer.write_polyline(ring, layer="WALLS", closed=True)

    # 3. Doors
    doors = schema.get("doors", [])
    for door in doors:
        pos = door["position"]
        px, py = pos["x"], pos["y"]
        dw = door["width_ft"]
        is_vert = door["orientation"] == "vertical"
        
        # Draw door opening line and simplified leaf
        if is_vert:
            writer.write_line(px, py - dw/2, px, py + dw/2, layer="DOORS")
            # Swing line
            writer.write_line(px, py - dw/2, px + dw * 0.86, py - dw/2 + dw * 0.5, layer="DOORS")
        else:
            writer.write_line(px - dw/2, py, px + dw/2, py, layer="DOORS")
            # Swing line
            writer.write_line(px - dw/2, py, px - dw/2 + dw * 0.5, py + dw * 0.86, layer="DOORS")

    # 4. Windows
    windows = schema.get("windows", [])
    for win in windows:
        pos = win["position"]
        px, py = pos["x"], pos["y"]
        ww = win["width_ft"]
        is_vert = win["orientation"] == "vertical"
        thick = 0.5  # 6 inches

        # Draw a double line box representing a standard sliding window
        if is_vert:
            writer.write_polyline([
                (px - thick/2, py - ww/2),
                (px + thick/2, py - ww/2),
                (px + thick/2, py + ww/2),
                (px - thick/2, py + ww/2)
            ], layer="WINDOWS", closed=True)
            writer.write_line(px, py - ww/2, px, py + ww/2, layer="WINDOWS")
        else:
            writer.write_polyline([
                (px - ww/2, py - thick/2),
                (px + ww/2, py - thick/2),
                (px + ww/2, py + thick/2),
                (px - ww/2, py + thick/2)
            ], layer="WINDOWS", closed=True)
            writer.write_line(px - ww/2, py, px + ww/2, py, layer="WINDOWS")

    # 5. Columns
    structural = schema.get("structural", {})
    columns = structural.get("columns", [])
    for col in columns:
        cx, cy = col["cx"], col["cy"]
        cw, ch = col["width"], col["height"]
        x, y = cx - cw/2, cy - ch/2
        pts = [(x, y), (x + cw, y), (x + cw, y + ch), (x, y + ch)]
        writer.write_polyline(pts, layer="COLUMNS", closed=True)
        # Draw crossed lines inside columns
        writer.write_line(x, y, x + cw, y + ch, layer="COLUMNS")
        writer.write_line(x + cw, y, x, y + ch, layer="COLUMNS")

    # 6. Beams
    beams = structural.get("beams", [])
    for beam in beams:
        writer.write_line(beam["x1"], beam["y1"], beam["x2"], beam["y2"], layer="BEAMS")

    # 7. Fixtures
    fixtures = schema.get("fixtures", [])
    for fix in fixtures:
        fx, fy = fix["x"], fix["y"]
        fw, fh = fix["width"], fix["height"]
        
        if fix["type"] == "toilet":
            # Tank
            writer.write_polyline([(fx, fy), (fx + fw, fy), (fx + fw, fy + fh*0.25), (fx, fy + fh*0.25)], layer="FIXTURES", closed=True)
            # Bowl
            writer.write_polyline([(fx + fw*0.1, fy + fh*0.25), (fx + fw*0.9, fy + fh*0.25), (fx + fw*0.7, fy + fh), (fx + fw*0.3, fy + fh)], layer="FIXTURES", closed=True)
        elif fix["type"] == "washbasin":
            writer.write_polyline([(fx, fy), (fx + fw, fy), (fx + fw, fy + fh), (fx, fy + fh)], layer="FIXTURES", closed=True)
        elif fix["type"] == "counter_l":
            # Kitchen L-countertop
            writer.write_polyline([(fx, fy), (fx + fw, fy), (fx + fw, fy + 2.0), (fx + 2.0, fy + 2.0), (fx + 2.0, fy + fh), (fx, fy + fh)], layer="FIXTURES", closed=True)

    # 8. Furniture
    furniture = schema.get("furniture", [])
    for furn in furniture:
        fx, fy = furn["x"], furn["y"]
        fw, fh = furn["width"], furn["height"]
        pts = [(fx, fy), (fx + fw, fy), (fx + fw, fy + fh), (fx, fy + fh)]
        writer.write_polyline(pts, layer="FURNITURE", closed=True)
        writer.write_text(furn["label"], fx + 0.2, fy + fh/2 - 0.1, height=0.2, layer="FURNITURE")

    writer.section_end()
    return writer.get_dxf_string()
