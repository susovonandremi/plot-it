import os
import sys
import json
from shapely.geometry import box as shapely_box

# Setup PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.services.site_context_engine import SiteContextEngine
from backend.services.architectural_core_solver import ArchitecturalCoreSolver
from backend.services.structural_engine import StructuralEngine
from backend.services.professional_svg_renderer import render_blueprint_professional

def verify_v6():
    print("🚀 Verifying Architectural Solver v6.0...")
    
    # 1. Site Context (1200sqft plot, East facing entry)
    plot_width_ft, plot_depth_ft = 30, 40
    FT_TO_M = 0.3048
    M_TO_FT = 3.28084
    
    site_engine = SiteContextEngine()
    site_context = site_engine.calculate_buildable_envelope(
        plot_width_m=plot_width_ft * FT_TO_M,
        plot_depth_m=plot_depth_ft * FT_TO_M,
        entry_direction='E'
    )
    
    print(f"📐 Envelope: {site_context['buildable_width']:.2f}m x {site_context['buildable_depth']:.2f}m")
    
    # 2. Rooms (3BHK Program)
    rooms = [
        {'type': 'LIVING', 'normalized_type': 'LIVING', 'area': 180},
        {'type': 'KITCHEN', 'normalized_type': 'KITCHEN', 'area': 100},
        {'type': 'BEDROOM 1', 'normalized_type': 'BEDROOM', 'area': 120},
        {'type': 'BEDROOM 2', 'normalized_type': 'BEDROOM', 'area': 120},
        {'type': 'BEDROOM 3', 'normalized_type': 'BEDROOM', 'area': 120},
        {'type': 'STAIRCASE', 'normalized_type': 'STAIRCASE', 'area': 70}
    ]
    
    # 3. Solve (V6.0 Core-First)
    solver = ArchitecturalCoreSolver(site_context['buildable_polygon'])
    floor_layout = solver.solve(rooms, 'E')
    
    # Convert to Feet
    for r in floor_layout:
        r['x'] = round(r['x'] * M_TO_FT, 2)
        r['y'] = round(r['y'] * M_TO_FT, 2)
        r['width'] = round(r['width'] * M_TO_FT, 2)
        r['height'] = round(r['height'] * M_TO_FT, 2)

    print(f"🏗️ Placed {len(floor_layout)} rooms.")
    
    # 4. Structural Engine
    structural_engine = StructuralEngine(plot_width_ft, plot_depth_ft)
    struct_res = structural_engine.analyze(floor_layout)
    print(f"🏗️ Placed {len(struct_res['columns'])} columns.")
    
    # 5. Render
    svg = render_blueprint_professional(
        placement_data=floor_layout,
        plot_width=plot_width_ft,
        plot_height=plot_depth_ft,
        vastu_score={'overall': 85},
        heavy_elements=struct_res
    )
    
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'v6_test_blueprint.svg'))
    with open(out_path, 'w') as f:
        f.write(svg)
    
    print(f"✅ V6.0 Verification Complete: {out_path}")

if __name__ == "__main__":
    verify_v6()
