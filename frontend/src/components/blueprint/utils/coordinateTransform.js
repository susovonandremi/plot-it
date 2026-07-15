// frontend/src/components/blueprint/utils/coordinateTransform.js
export const SCALE = 30.0;       // 30 pixels per foot
export const PADDING = 80.0;     // Margin around floor plan

export function ftToPx(ft, offset = PADDING) {
  return offset + ft * SCALE;
}

export function computeViewBox(schema) {
  if (!schema || !schema.metadata) return "0 0 1000 1000";
  const { plot_width_ft, plot_height_ft } = schema.metadata;
  const w = plot_width_ft * SCALE + 2 * PADDING;
  const h = plot_height_ft * SCALE + 2 * PADDING + 120; // 120px for title block
  return `0 0 ${w} ${h}`;
}

export function formatDimension(valueFt, unitSystem = "imperial") {
  if (unitSystem === "metric") {
    // 1 ft = 304.8 mm
    const valMm = Math.round(valueFt * 304.8);
    return `${valMm}`;
  } else {
    const totalInches = Math.round(valueFt * 12);
    const ft = Math.floor(totalInches / 12);
    const inches = totalInches % 12;
    return `${ft}'-${String(inches).padStart(2, '0')}"`;
  }
}
