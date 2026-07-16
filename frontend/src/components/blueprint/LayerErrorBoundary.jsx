// frontend/src/components/blueprint/LayerErrorBoundary.jsx
import React from 'react';

/**
 * Micro error boundary for individual SVG layer components.
 *
 * If a layer (e.g., FurnitureLayer, StructuralLayer) throws during render,
 * this boundary catches the error and renders nothing — the rest of the
 * blueprint remains intact.
 *
 * Usage:
 *   <LayerErrorBoundary layerName="furniture">
 *     <FurnitureLayer ... />
 *   </LayerErrorBoundary>
 */
export default class LayerErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.warn(
      `[Blueprint] Layer "${this.props.layerName || 'unknown'}" crashed and was hidden:`,
      error,
      errorInfo
    );
  }

  render() {
    if (this.state.hasError) {
      // Render nothing — the layer silently disappears, but the rest of
      // the blueprint (rooms, walls, labels, etc.) continues to render.
      return null;
    }
    return this.props.children;
  }
}
