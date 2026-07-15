// frontend/src/components/blueprint/symbols.jsx
import React from 'react';
import { ftToPx, SCALE } from './utils/coordinateTransform';

const INK_COLOR = "#000000";
const DIM_COLOR = "#334155";

export function ColumnSymbol({ cx, cy, width, height, reason }) {
  const w = width * SCALE;
  const h = height * SCALE;
  const x = ftToPx(cx) - w / 2;
  const y = ftToPx(cy) - h / 2;

  return (
    <g className="column-symbol">
      {/* Solid filled structural column */}
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        fill="#1e293b"
        stroke={INK_COLOR}
        strokeWidth={1}
      />
      {/* Hatch/Cross-hatch pattern inside columns */}
      <line x1={x} y1={y} x2={x + w} y2={y + h} stroke="#fff" strokeWidth={0.5} opacity={0.5} />
      <line x1={x + w} y1={y} x2={x} y2={y + h} stroke="#fff" strokeWidth={0.5} opacity={0.5} />
    </g>
  );
}

export function DoorSymbol({ x, y, width, orientation, doorType }) {
  if (doorType !== 'main') {
    // Normal interior doors are rendered as completely blank gaps in the wall polygon.
    return null;
  }

  const px = ftToPx(x);
  const py = ftToPx(y);
  const isVert = orientation === 'vertical';

  return (
    <g className="entry-point-symbol">
      {/* Premium Teal entrance arrow pointing into the doorway */}
      {isVert ? (
        // Vertical entry door (on West or East wall)
        <g>
          <path
            d={px < 150 ? `M ${px - 25} ${py} L ${px - 5} ${py} M ${px - 12} ${py - 6} L ${px - 5} ${py} L ${px - 12} ${py + 6}` : `M ${px + 25} ${py} L ${px + 5} ${py} M ${px + 12} ${py - 6} L ${px + 5} ${py} L ${px + 12} ${py + 6}`}
            stroke="#0f766e"
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
          <text
            x={px < 150 ? px - 32 : px + 32}
            y={py + 3}
            fontSize={9}
            fontWeight="900"
            fill="#0f766e"
            textAnchor={px < 150 ? "end" : "start"}
            fontFamily="'Inter', 'Outfit', sans-serif"
            letterSpacing="0.05em"
          >
            ENTRY
          </text>
        </g>
      ) : (
        // Horizontal entry door (on North or South wall)
        <g>
          <path
            d={py < 150 ? `M ${px} ${py - 25} L ${px} ${py - 5} M ${px - 6} ${py - 12} L ${px} ${py - 5} L ${px + 6} ${py - 12}` : `M ${px} ${py + 25} L ${px} ${py + 5} M ${px - 6} ${py + 12} L ${px} ${py + 5} L ${px + 6} ${py + 12}`}
            stroke="#0f766e"
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
          <text
            x={px}
            y={py < 150 ? py - 32 : py + 34}
            fontSize={9}
            fontWeight="900"
            fill="#0f766e"
            textAnchor="middle"
            fontFamily="'Inter', 'Outfit', sans-serif"
            letterSpacing="0.05em"
          >
            ENTRY
          </text>
        </g>
      )}
    </g>
  );
}

export function WindowSymbol({ x, y, width, orientation }) {
  const px = ftToPx(x);
  const py = ftToPx(y);
  const ww = width * SCALE;
  const thick = 0.5 * SCALE; // 6 inches in pixels

  const isVert = orientation === 'vertical';

  return (
    <g className="window-symbol">
      {isVert ? (
        <>
          {/* Inner glass/sash lines */}
          <rect
            x={px - thick / 2}
            y={py - ww / 2}
            width={thick}
            height={ww}
            fill="#e2e8f0"
            stroke={INK_COLOR}
            strokeWidth={1}
          />
          <line x1={px} y1={py - ww / 2} x2={px} y2={py + ww / 2} stroke={INK_COLOR} strokeWidth={0.75} />
        </>
      ) : (
        <>
          <rect
            x={px - ww / 2}
            y={py - thick / 2}
            width={ww}
            height={thick}
            fill="#e2e8f0"
            stroke={INK_COLOR}
            strokeWidth={1}
          />
          <line x1={px - ww / 2} y1={py} x2={px + ww / 2} y2={py} stroke={INK_COLOR} strokeWidth={0.75} />
        </>
      )}
    </g>
  );
}

export function ToiletSymbol({ x, y }) {
  const wx = ftToPx(x);
  const wy = ftToPx(y);
  const wc_w = 1.6 * SCALE;
  const wc_h = 2.4 * SCALE;
  const bowl_y = wy + wc_h * 0.25;

  return (
    <g className="toilet-fixture">
      {/* Tank */}
      <rect
        x={wx}
        y={wy}
        width={wc_w}
        height={wc_h * 0.25}
        fill="#ffffff"
        stroke={DIM_COLOR}
        strokeWidth={1}
        rx={2}
      />
      {/* Bowl */}
      <path
        d={`M ${wx + wc_w*0.1} ${bowl_y} Q ${wx + wc_w*0.05} ${bowl_y + wc_h*0.7} ${wx + wc_w*0.5} ${bowl_y + wc_h*0.7} Q ${wx + wc_w*0.95} ${bowl_y + wc_h*0.7} ${wx + wc_w*0.9} ${bowl_y} Z`}
        fill="#ffffff"
        stroke={DIM_COLOR}
        strokeWidth={1}
      />
      <ellipse
        cx={wx + wc_w / 2}
        cy={bowl_y + wc_h * 0.3}
        rx={wc_w * 0.3}
        ry={wc_h * 0.2}
        fill="none"
        stroke={DIM_COLOR}
        strokeWidth={0.5}
        opacity={0.5}
      />
    </g>
  );
}

export function WashbasinSymbol({ x, y }) {
  const bx = ftToPx(x);
  const by = ftToPx(y);
  const basin_w = 1.8 * SCALE;
  const basin_h = 1.4 * SCALE;

  return (
    <g className="washbasin-fixture">
      {/* Outer counter */}
      <rect
        x={bx}
        y={by}
        width={basin_w}
        height={basin_h}
        fill="#ffffff"
        stroke={DIM_COLOR}
        strokeWidth={1}
        rx={4}
      />
      {/* Inner bowl */}
      <ellipse
        cx={bx + basin_w / 2}
        cy={by + basin_h / 2}
        rx={basin_w * 0.35}
        ry={basin_h * 0.3}
        fill="#ffffff"
        stroke={DIM_COLOR}
        strokeWidth={0.75}
      />
      {/* Tap dot */}
      <circle cx={bx + basin_w / 2} cy={by + 4} r={2} fill={DIM_COLOR} />
    </g>
  );
}

export function KitchenCounterSymbol({ x, y, width, height }) {
  const kx = ftToPx(x);
  const ky = ftToPx(y);
  const kw = width * SCALE;
  const kh = height * SCALE;
  const depth = 2.0 * SCALE; // Standard 2ft counter depth

  // Standard L-shaped path along top and left walls
  const dPath = `M ${kx} ${ky} L ${kx + kw} ${ky} L ${kx + kw} ${ky + depth} L ${kx + depth} ${ky + depth} L ${kx + depth} ${ky + kh} L ${kx} ${ky + kh} Z`;

  // Sink position (mid of vertical leg)
  const sx = kx + (depth - 1.6 * SCALE) / 2;
  const sy = ky + kh * 0.5 - 1.25 * SCALE;
  const sw = 1.6 * SCALE;
  const sh = 2.5 * SCALE;

  // Stove/Hob position (mid of horizontal leg)
  const hx = kx + kw * 0.6 - 1.1 * SCALE;
  const hy = ky + (depth - 1.8 * SCALE) / 2;
  const hw = 2.2 * SCALE;
  const hh = 1.8 * SCALE;

  return (
    <g className="kitchen-counter-symbol">
      {/* L-Shape Countertop */}
      <path
        d={dPath}
        fill="#ffffff"
        stroke={DIM_COLOR}
        strokeWidth={1.5}
      />
      <path
        d={`M ${kx + 2} ${ky + depth - 2} L ${kx + kw - 2} ${ky + depth - 2}`}
        fill="none"
        stroke={DIM_COLOR}
        strokeWidth={0.5}
        opacity={0.4}
      />

      {/* Stove/Hob detail */}
      <rect
        x={hx}
        y={hy}
        width={hw}
        height={hh}
        fill="#1e293b"
        stroke={DIM_COLOR}
        strokeWidth={1}
        rx={2}
      />
      {/* 4 Burners */}
      <circle cx={hx + 8} cy={hy + 6} r={4} fill="#64748b" stroke={DIM_COLOR} strokeWidth={0.5} />
      <circle cx={hx + hw - 8} cy={hy + 6} r={4} fill="#64748b" stroke={DIM_COLOR} strokeWidth={0.5} />
      <circle cx={hx + 8} cy={hy + hh - 6} r={4} fill="#64748b" stroke={DIM_COLOR} strokeWidth={0.5} />
      <circle cx={hx + hw - 8} cy={hy + hh - 6} r={4} fill="#64748b" stroke={DIM_COLOR} strokeWidth={0.5} />

      {/* Dual Basin Sink */}
      <rect
        x={sx}
        y={sy}
        width={sw}
        height={sh}
        fill="#ffffff"
        stroke={DIM_COLOR}
        strokeWidth={1}
        rx={2}
      />
      <rect x={sx + 3} y={sy + 3} width={sw - 6} height={sh / 2 - 4} fill="none" stroke={DIM_COLOR} strokeWidth={0.5} />
      <rect x={sx + 3} y={sy + sh / 2 + 1} width={sw - 6} height={sh / 2 - 4} fill="none" stroke={DIM_COLOR} strokeWidth={0.5} />
    </g>
  );
}

export function StaircaseSymbol({ x, y, width, height }) {
  const sx = ftToPx(x);
  const sy = ftToPx(y);
  const sw = width * SCALE;
  const sh = height * SCALE;

  // Let's render parallel tread lines for staircase
  const numTreads = 10;
  const step = sw / numTreads;
  const lines = [];

  for (let i = 1; i < numTreads; i++) {
    const tx = sx + i * step;
    lines.push(
      <line
        key={i}
        x1={tx}
        y1={sy}
        x2={tx}
        y2={sy + sh}
        stroke={INK_COLOR}
        strokeWidth={0.5}
      />
    );
  }

  return (
    <g className="staircase-symbol">
      {/* Outer bounding Box */}
      <rect
        x={sx}
        y={sy}
        width={sw}
        height={sh}
        fill="none"
        stroke={INK_COLOR}
        strokeWidth={1}
      />
      {/* Stair Treads */}
      {lines}
      {/* Center line with arrow */}
      <line
        x1={sx + sw * 0.1}
        y1={sy + sh / 2}
        x2={sx + sw * 0.9}
        y2={sy + sh / 2}
        stroke={INK_COLOR}
        strokeWidth={0.75}
      />
      <path
        d={`M ${sx + sw * 0.9} ${sy + sh / 2} L ${sx + sw * 0.8} ${sy + sh / 2 - 4} L ${sx + sw * 0.8} ${sy + sh / 2 + 4} Z`}
        fill={INK_COLOR}
      />
    </g>
  );
}

export function LiftSymbol({ x, y, width, height }) {
  const lx = ftToPx(x);
  const ly = ftToPx(y);
  const lw = width * SCALE;
  const lh = height * SCALE;

  return (
    <g className="lift-symbol">
      {/* Outer framing box */}
      <rect
        x={lx}
        y={ly}
        width={lw}
        height={lh}
        fill="none"
        stroke={INK_COLOR}
        strokeWidth={1.5}
      />
      {/* Diagonal crosses (CAD drafting lift convention) */}
      <line x1={lx} y1={ly} x2={lx + lw} y2={ly + lh} stroke={INK_COLOR} strokeWidth={0.5} />
      <line x1={lx + lw} y1={ly} x2={lx} y2={ly + lh} stroke={INK_COLOR} strokeWidth={0.5} />
    </g>
  );
}
