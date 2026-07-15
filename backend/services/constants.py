# backend/services/constants.py
"""
Centralized Geometric & Tolerance Constants
============================================
Single source of truth for all tolerance values used across
the PlotIt layout engine pipeline. Import these instead of
declaring local TOL / TOLERANCE variables.
"""

# ── Geometric Tolerances (in feet) ────────────────────────────────────────────

# Wall adjacency tolerance — 6-inch (0.5 ft)
# Used for room-to-wall proximity checks, exterior wall detection,
# fixture snapping, and ventilation scoring.
WALL_ADJACENCY_TOL = 0.5

# Overlap tolerance — ~2-inch (0.15 ft)
# Used for floating-point rounding tolerance in geometric validation
# and wall segment merging.
OVERLAP_TOL = 0.15

# ── Diff Engine Tolerances (in feet) ──────────────────────────────────────────

# Position changes smaller than this are considered "unchanged"
POSITION_TOL = 1.0

# Size changes smaller than this are considered "unchanged"
SIZE_TOL = 2.0

# ── Solver Constants ──────────────────────────────────────────────────────────

# Half-foot grid: all solver variables are in units of 0.5 ft.
# This gives 6-inch precision, standard for Indian residential plans.
SOLVER_SCALE = 2  # 1 foot = 2 solver units
