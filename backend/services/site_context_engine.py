"""
Site Context Engine
===================
Calculates the BUILDABLE ENVELOPE before any layout begins.
A plot is never 100% buildable — municipal setbacks, common passages,
and road-facing margins reduce the usable area.

Verified from real G+3 Indian residential blueprint:
  - Road frontage (South side): public road, no building in road ROW
  - Common passage (one side): 3.60 M shared passage, cannot be built over
  - Structural setbacks mandated by Indian municipal building bylaws
"""

from typing import Dict, Optional
from shapely.geometry import box as shapely_box, Polygon


class SiteContextEngine:
    """
    Computes the buildable rectangle within a plot after applying
    municipal setback rules, common passage deductions, and
    road-facing margins.
    """

    # (road_width_threshold_m): (front_setback_m, side_setback_m, rear_setback_m)
    # Source: Standard Indian municipal building bylaws
    SETBACK_RULES = {
        'narrow_road':  (7.5,  (1.0, 0.5, 1.0)),   # road < 7.5 M
        'medium_road':  (15.0, (1.5, 1.0, 1.5)),    # road 7.5–15 M
        'wide_road':    (999,  (3.0, 1.5, 2.0)),    # road > 15 M
    }

    # FAR (Floor Area Ratio) limits by municipal zone — informational
    FAR_LIMITS = {
        'residential':  1.5,
        'commercial':   2.5,
        'mixed_use':    2.0,
    }

    def calculate_buildable_envelope(
        self,
        plot_width_m: float,
        plot_depth_m: float,
        road_width_m: float = 8.534,        # from blueprint (28 ft road)
        entry_direction: str = 'S',          # road is South in this case
        common_passage_m: float = 0.0,       # 3.60 M in blueprint
        passage_side: Optional[str] = None,  # 'W', 'E', 'N', 'S'
        building_type: str = 'residential',
    ) -> Dict:
        """
        Calculate the buildable rectangle within the plot.

        Args:
            plot_width_m:      Total plot width in meters
            plot_depth_m:      Total plot depth in meters
            road_width_m:      Width of the road abutting the plot
            entry_direction:   Direction of road/entry ('N', 'S', 'E', 'W')
            common_passage_m:  Width of shared common passage (0 if none)
            passage_side:      Which side the common passage is on
            building_type:     'residential', 'commercial', 'mixed_use'

        Returns:
            Dict with buildable rectangle geometry, setbacks, and coverage.
        """

        # ── 1. Select setback rule based on road width ────────────────────────
        if road_width_m < 7.5:
            rule = self.SETBACK_RULES['narrow_road']
        elif road_width_m < 15.0:
            rule = self.SETBACK_RULES['medium_road']
        else:
            rule = self.SETBACK_RULES['wide_road']

        front_sb, side_sb, rear_sb = rule[1]

        # ── 2. Apply common passage (adds to setback on that side) ────────────
        left_sb = side_sb
        right_sb = side_sb

        if passage_side == 'W':
            left_sb = max(left_sb, common_passage_m)
        elif passage_side == 'E':
            right_sb = max(right_sb, common_passage_m)
        elif passage_side == 'N':
            rear_sb = max(rear_sb, common_passage_m)
        elif passage_side == 'S':
            front_sb = max(front_sb, common_passage_m)

        # ── 3. Calculate buildable rectangle per entry direction ───────────────
        #
        # Convention:
        #   - "front" = road-facing side (entry_direction)
        #   - "rear"  = opposite of front
        #   - "left"/"right" = perpendicular sides
        #
        # Plot origin (0,0) is always top-left corner in our coordinate system.
        # X increases rightward, Y increases downward.

        if entry_direction == 'S':
            # Road is at the bottom (South). Front setback eats into bottom.
            buildable_x = left_sb
            buildable_y = rear_sb                              # rear is at top (North)
            buildable_w = plot_width_m - left_sb - right_sb
            buildable_d = plot_depth_m - front_sb - rear_sb

        elif entry_direction == 'N':
            # Road is at the top (North). Front setback eats into top.
            buildable_x = left_sb
            buildable_y = front_sb                             # front is at top (North)
            buildable_w = plot_width_m - left_sb - right_sb
            buildable_d = plot_depth_m - front_sb - rear_sb

        elif entry_direction == 'E':
            # Road is at the right (East). Front setback eats into right.
            buildable_x = rear_sb
            buildable_y = left_sb
            buildable_w = plot_width_m - front_sb - rear_sb
            buildable_d = plot_depth_m - left_sb - right_sb

        elif entry_direction == 'W':
            # Road is at the left (West). Front setback eats into left.
            buildable_x = front_sb
            buildable_y = left_sb
            buildable_w = plot_width_m - front_sb - rear_sb
            buildable_d = plot_depth_m - left_sb - right_sb

        else:
            # Fallback: uniform setback
            buildable_x = side_sb
            buildable_y = front_sb
            buildable_w = plot_width_m - 2 * side_sb
            buildable_d = plot_depth_m - front_sb - rear_sb

        # Clamp to positive values
        buildable_w = max(buildable_w, 1.0)
        buildable_d = max(buildable_d, 1.0)

        plot_area_sqm = plot_width_m * plot_depth_m
        buildable_area_sqm = buildable_w * buildable_d
        ground_coverage_pct = (buildable_area_sqm / plot_area_sqm) * 100 if plot_area_sqm > 0 else 0

        # FAR check (informational)
        far_limit = self.FAR_LIMITS.get(building_type, 1.5)

        buildable_poly = shapely_box(
            buildable_x, buildable_y, 
            buildable_x + buildable_w, 
            buildable_y + buildable_d
        )

        return {
            'buildable_x': round(buildable_x, 3),
            'buildable_y': round(buildable_y, 3),
            'buildable_width': round(buildable_w, 3),
            'buildable_depth': round(buildable_d, 3),
            'buildable_area_sqm': round(buildable_area_sqm, 2),
            'buildable_area_sqft': round(buildable_area_sqm * 10.7639, 2),
            'buildable_polygon': buildable_poly,
            'plot_area_sqm': round(plot_area_sqm, 2),
            'plot_area_sqft': round(plot_area_sqm * 10.7639, 2),
            'setbacks': {
                'front': round(front_sb, 3),
                'rear': round(rear_sb, 3),
                'left': round(left_sb, 3),
                'right': round(right_sb, 3),
            },
            'ground_coverage_pct': round(ground_coverage_pct, 1),
            'far_limit': far_limit,
            'road_width_m': road_width_m,
            'entry_direction': entry_direction,
            'common_passage_m': common_passage_m,
            'passage_side': passage_side,
        }

    def convert_buildable_to_feet(self, envelope: Dict) -> Dict:
        """
        Convenience: returns buildable dimensions in feet for the
        BSP engine (which works in feet).
        """
        M_TO_FT = 3.28084
        return {
            'buildable_x_ft': round(envelope['buildable_x'] * M_TO_FT, 2),
            'buildable_y_ft': round(envelope['buildable_y'] * M_TO_FT, 2),
            'buildable_width_ft': round(envelope['buildable_width'] * M_TO_FT, 2),
            'buildable_depth_ft': round(envelope['buildable_depth'] * M_TO_FT, 2),
        }
