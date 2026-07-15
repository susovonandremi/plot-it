// frontend/src/components/blueprint/layers.jsx
import React from 'react';
import { ftToPx, formatDimension, SCALE, PADDING } from './utils/coordinateTransform';
import { 
  DoorSymbol, WindowSymbol, ToiletSymbol, WashbasinSymbol, 
  KitchenCounterSymbol, ColumnSymbol, StaircaseSymbol, LiftSymbol 
} from './symbols';

const INK_COLOR = "#000000";
const DIM_COLOR = "#334155";

export function wktToSvgPath(wkt) {
  if (!wkt) return "";
  // Extract coordinate rings
  const rings = wkt.match(/\([^()]*\)/g);
  if (!rings) return "";

  let pathData = "";
  for (const ring of rings) {
    const coords = ring.replace(/[()]/g, "").trim().split(/\s*,\s*/);
    let command = "M";
    for (const coord of coords) {
      const parts = coord.trim().split(/\s+/);
      if (parts.length !== 2) continue;
      const x = ftToPx(parseFloat(parts[0]));
      const y = ftToPx(parseFloat(parts[1]));
      pathData += `${command} ${x} ${y} `;
      command = "L";
    }
    pathData += "Z ";
  }
  return pathData.trim();
}

export function RoomLayer({ rooms = [], unitSystem, visible = true }) {
  if (!visible) return null;

  const ROOM_COLORS = {
    'living':         '#FFF8F0',
    'dining':         '#FFF8F0',
    'bedroom':        '#F0F4FF',
    'master_bedroom': '#F0F4FF',
    'bathroom':       '#F0F8FF',
    'kitchen':        '#FFFFF0',
    'pooja':          '#FFF5E6',
    'study':          '#F5F0FF',
    'garage':         '#F5F5F5',
    'entrance':       '#F8F8F0',
    'foyer':          '#F8F8F0',
    'hallway':        '#F5F5F5',
    'passage':        '#F5F5F5',
    'staircase':      '#F0F0F0',
    'lift':           '#F0F0F0',
    'verandah':       '#F0FAF0',
    'balcony':        '#F0FAF0',
    'open_terrace':   '#F0FAF0',
    'car_parking':    '#F5F5F5',
  };

  return (
    <g data-layer="rooms" className="layer-rooms">
      {rooms.map((room) => {
        const x = ftToPx(room.x);
        const y = ftToPx(room.y);
        const w = room.width * SCALE;
        const h = room.height * SCALE;
        const color = ROOM_COLORS[room.type] || "#ffffff";

        return (
          <g key={room.id}>
            {/* Filled room background */}
            <rect
              x={x}
              y={y}
              width={w}
              height={h}
              fill={color}
              stroke="#e2e8f0"
              strokeWidth={1}
            />
          </g>
        );
      })}
    </g>
  );
}

export function WallLayer({ walls, visible = true }) {
  if (!visible) return null;

  const dPath = wktToSvgPath(walls.boundary_polygon_wkt);

  return (
    <g data-layer="walls" className="layer-walls">
      {/* Structural wall geometry represented as SVG <path> with evenodd rule */}
      <path
        d={dPath}
        fill="url(#wall-hatch)"
        stroke={INK_COLOR}
        strokeWidth={1.5}
        fillRule="evenodd"
      />
    </g>
  );
}

export function DoorLayer({ doors = [], visible = true }) {
  if (!visible) return null;

  return (
    <g data-layer="doors" className="layer-doors">
      {doors.map((door) => (
        <DoorSymbol
          key={door.id}
          x={door.position.x}
          y={door.position.y}
          width={door.width_ft}
          orientation={door.orientation}
          doorType={door.door_type}
        />
      ))}
    </g>
  );
}

export function WindowLayer({ windows = [], visible = true }) {
  if (!visible) return null;

  return (
    <g data-layer="windows" className="layer-windows">
      {windows.map((win) => (
        <WindowSymbol
          key={win.id}
          x={win.position.x}
          y={win.position.y}
          width={win.width_ft}
          orientation={win.orientation}
        />
      ))}
    </g>
  );
}

export function LabelLayer({ rooms = [], unitSystem, visible = true }) {
  if (!visible) return null;

  return (
    <g data-layer="labels" className="layer-labels">
      {rooms.map((room) => {
        const cx = ftToPx(room.x + room.width / 2);
        const cy = ftToPx(room.y + room.height / 2);
        const labelText = room.label;
        const dimText = `${formatDimension(room.width, unitSystem)} × ${formatDimension(room.height, unitSystem)}`;

        // Don't render labels for tiny annotations/passages
        if (room.width < 3 || room.height < 3) return null;

        return (
          <g key={room.id} className="room-label-block">
            {/* Room Name */}
            <text
              x={cx}
              y={cy - 4}
              textAnchor="middle"
              fontFamily="Arial, sans-serif"
              fontSize="10px"
              fontWeight="bold"
              fill={INK_COLOR}
            >
              {labelText}
            </text>
            {/* Room Dimensions */}
            <text
              x={cx}
              y={cy + 8}
              textAnchor="middle"
              fontFamily="Arial, sans-serif"
              fontSize="8px"
              fontWeight="normal"
              fill={DIM_COLOR}
              opacity={0.8}
            >
              {dimText}
            </text>
          </g>
        );
      })}
    </g>
  );
}

export function StructuralLayer({ structural, visible = true }) {
  if (!visible || !structural) return null;
  const beams = structural.beams || [];
  const columns = structural.columns || [];

  return (
    <g data-layer="structural" className="layer-structural">
      {/* Connect columns with load-bearing beams */}
      {beams.map((beam) => (
        <line
          key={beam.id}
          x1={ftToPx(beam.x1)}
          y1={ftToPx(beam.y1)}
          x2={ftToPx(beam.x2)}
          y2={ftToPx(beam.y2)}
          stroke="#475569"
          strokeWidth={2}
          strokeDasharray="4,2"
          opacity={0.6}
        />
      ))}
      
      {/* Placed Column RCC markers */}
      {columns.map((col) => (
        <ColumnSymbol
          key={col.id}
          cx={col.cx}
          cy={col.cy}
          width={col.width}
          height={col.height}
          reason={col.reason}
        />
      ))}
    </g>
  );
}

export function FixtureLayer({ fixtures = [], visible = true }) {
  if (!visible) return null;

  return (
    <g data-layer="fixtures" className="layer-fixtures">
      {fixtures.map((fix) => {
        if (fix.type === "toilet") {
          return <ToiletSymbol key={fix.id} x={fix.x} y={fix.y} />;
        } else if (fix.type === "washbasin") {
          return <WashbasinSymbol key={fix.id} x={fix.x} y={fix.y} />;
        } else if (fix.type === "counter_l") {
          return (
            <KitchenCounterSymbol
              key={fix.id}
              x={fix.x}
              y={fix.y}
              width={fix.width}
              height={fix.height}
            />
          );
        }
        return null;
      })}
    </g>
  );
}

export function FurnitureLayer({ furniture = [], visible = true }) {
  if (!visible) return null;

  return (
    <g data-layer="furniture" className="layer-furniture">
      {furniture.map((furn) => {
        const fx = ftToPx(furn.x);
        const fy = ftToPx(furn.y);
        const fw = furn.width * SCALE;
        const fh = furn.height * SCALE;

        // Simplified CAD representation of furniture blocks
        return (
          <g key={furn.id} transform={`rotate(${furn.rotation_deg}, ${fx + fw/2}, ${fy + fh/2})`}>
            {/* Outer box of the furniture item */}
            <rect
              x={fx}
              y={fy}
              width={fw}
              height={fh}
              fill="#f8fafc"
              stroke={DIM_COLOR}
              strokeWidth={0.75}
              rx={1}
            />
            {/* Label inside the block */}
            <text
              x={fx + fw / 2}
              y={fy + fh / 2 + 3}
              textAnchor="middle"
              fontFamily="Arial, sans-serif"
              fontSize="6px"
              fill={DIM_COLOR}
              opacity={0.6}
            >
              {furn.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}

export function DimensionLayer({ dimensionChains, visible = true }) {
  if (!visible || !dimensionChains) return null;

  const overall_width = dimensionChains.overall_width || { value_ft: 0, label: "" };
  const overall_depth = dimensionChains.overall_depth || { value_ft: 0, label: "" };
  const top_facade = dimensionChains.top_facade || [];
  const left_facade = dimensionChains.left_facade || [];

  const tickStyle = { stroke: INK_COLOR, strokeWidth: 0.7 };

  return (
    <g data-layer="dimensions" className="layer-dimensions">
      {/* 1. Overall plot width at the top facade */}
      {(() => {
        const dimY = PADDING - 40;
        const startX = PADDING;
        const endX = PADDING + overall_width.value_ft * SCALE;

        return (
          <g className="dimension-overall-width">
            <line x1={startX} y1={dimY} x2={endX} y2={dimY} stroke={INK_COLOR} strokeWidth={0.5} />
            <line x1={startX - 3} y1={dimY + 3} x2={startX + 3} y2={dimY - 3} {...tickStyle} />
            <line x1={endX - 3} y1={dimY + 3} x2={endX + 3} y2={dimY - 3} {...tickStyle} />
            <text
              x={(startX + endX) / 2}
              y={dimY - 4}
              textAnchor="middle"
              fontFamily="Arial, sans-serif"
              fontSize="9px"
              fill={INK_COLOR}
            >
              {overall_width.label}
            </text>
          </g>
        );
      })()}

      {/* 2. Overall plot depth along the left side */}
      {(() => {
        const dimX = PADDING - 40;
        const startY = PADDING;
        const endY = PADDING + overall_depth.value_ft * SCALE;

        return (
          <g className="dimension-overall-depth">
            <line x1={dimX} y1={startY} x2={dimX} y2={endY} stroke={INK_COLOR} strokeWidth={0.5} />
            <line x1={dimX - 3} y1={startY + 3} x2={dimX + 3} y2={startY - 3} {...tickStyle} />
            <line x1={dimX - 3} y1={endY + 3} x2={dimX + 3} y2={endY - 3} {...tickStyle} />
            <text
              x={dimX - 6}
              y={(startY + endY) / 2 + 3}
              textAnchor="end"
              fontFamily="Arial, sans-serif"
              fontSize="9px"
              fill={INK_COLOR}
            >
              {overall_depth.label}
            </text>
          </g>
        );
      })()}

      {/* 3. Room-by-room top facade dimension segment chains */}
      {top_facade.map((seg, idx) => {
        const sx = ftToPx(seg.start_ft);
        const ex = ftToPx(seg.end_ft);
        const y = PADDING - 20;

        return (
          <g key={idx} className="dimension-top-segment">
            <line x1={sx} y1={y} x2={ex} y2={y} stroke={INK_COLOR} strokeWidth={0.5} />
            <line x1={sx - 2} y1={y + 2} x2={sx + 2} y2={y - 2} {...tickStyle} strokeWidth={0.5} />
            <line x1={ex - 2} y1={y + 2} x2={ex + 2} y2={y - 2} {...tickStyle} strokeWidth={0.5} />
            <text
              x={(sx + ex) / 2}
              y={y - 3}
              textAnchor="middle"
              fontFamily="Arial, sans-serif"
              fontSize="8px"
              fill={DIM_COLOR}
            >
              {seg.label}
            </text>
          </g>
        );
      })}

      {/* 4. Room-by-room left facade dimension segment chains */}
      {left_facade.map((seg, idx) => {
        const sy = ftToPx(seg.start_ft);
        const ey = ftToPx(seg.end_ft);
        const x = PADDING - 20;

        return (
          <g key={idx} className="dimension-left-segment">
            <line x1={x} y1={sy} x2={x} y2={ey} stroke={INK_COLOR} strokeWidth={0.5} />
            <line x1={x - 2} y1={sy + 2} x2={x + 2} y2={sy - 2} {...tickStyle} strokeWidth={0.5} />
            <line x1={x - 2} y1={ey + 2} x2={x + 2} y2={ey - 2} {...tickStyle} strokeWidth={0.5} />
            <text
              x={x - 5}
              y={(sy + ey) / 2 + 3}
              textAnchor="end"
              fontFamily="Arial, sans-serif"
              fontSize="8px"
              fill={DIM_COLOR}
            >
              {seg.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}

export function AnnotationLayer({ schema, visible = true }) {
  if (!visible || !schema || !schema.metadata) return null;

  const { metadata, site_context } = schema;
  const { plot_width_ft, plot_height_ft, floor_label, vastu_score } = metadata;
  
  const w = plot_width_ft * SCALE + 2 * PADDING;
  const h = plot_height_ft * SCALE + 2 * PADDING + 120;
  const blockY = h - 90;

  return (
    <g data-layer="annotations" className="layer-annotations">
      {/* 1. Compass Rose (Drafting style North Arrow) in top right */}
      <g transform={`translate(${w - PADDING}, ${PADDING})`}>
        <circle cx={0} cy={0} r={15} fill="none" stroke={INK_COLOR} strokeWidth={1} />
        <line x1={0} y1={12} x2={0} y2={-20} stroke="#ef4444" strokeWidth={1.5} />
        <polygon points="0,-22 -4,-15 4,-15" fill="#ef4444" />
        <text x={0} y={-26} textAnchor="middle" fontFamily="Arial, sans-serif" fontSize="10px" fontWeight="bold" fill="#ef4444">N</text>
      </g>

      {/* 2. Scale Bar in bottom left */}
      <g transform={`translate(${PADDING}, ${h - 110})`}>
        <line x1={0} y1={0} x2={150} y2={0} stroke={INK_COLOR} strokeWidth={1.5} />
        <line x1={0} y1={-3} x2={0} y2={3} stroke={INK_COLOR} strokeWidth={1} />
        <line x1={75} y1={-3} x2={75} y2={3} stroke={INK_COLOR} strokeWidth={1} />
        <line x1={150} y1={-3} x2={150} y2={3} stroke={INK_COLOR} strokeWidth={1} />
        <text x={0} y={10} textAnchor="middle" fontFamily="Arial, sans-serif" fontSize="7px" fill={DIM_COLOR}>0</text>
        <text x={75} y={10} textAnchor="middle" fontFamily="Arial, sans-serif" fontSize="7px" fill={DIM_COLOR}>2.5m / 8.2ft</text>
        <text x={150} y={10} textAnchor="middle" fontFamily="Arial, sans-serif" fontSize="7px" fill={DIM_COLOR}>5m / 16.4ft</text>
      </g>

      {/* 3. Title Block at bottom */}
      <g className="title-block">
        <rect
          x={PADDING}
          y={blockY}
          width={w - 2 * PADDING}
          height={60}
          fill="#ffffff"
          stroke={INK_COLOR}
          strokeWidth={1}
        />
        {/* Plan Title */}
        <text
          x={PADDING + 20}
          y={blockY + 25}
          fontFamily="Archivo, sans-serif"
          fontSize="14px"
          fontWeight="bold"
          fill={INK_COLOR}
        >
          {floor_label}
        </text>
        {/* Plot Area */}
        <text
          x={PADDING + 20}
          y={blockY + 45}
          fontFamily="Inter, sans-serif"
          fontSize="9px"
          fontWeight="500"
          fill={DIM_COLOR}
        >
          {`TOTAL PLOT AREA: ${(plot_width_ft * plot_height_ft).toFixed(2)} SQFT / ${(plot_width_ft * plot_height_ft * 0.092903).toFixed(2)} SQM`}
        </text>
        {/* Vastu Score Badge */}
        <text
          x={w - PADDING - 20}
          y={blockY + 35}
          textAnchor="end"
          fontFamily="Archivo, sans-serif"
          fontSize="10px"
          fontWeight="bold"
          fill={INK_COLOR}
        >
          {`Vastu Compliance: ${vastu_score.overall || vastu_score.score || 0}%`}
        </text>
      </g>
    </g>
  );
}
