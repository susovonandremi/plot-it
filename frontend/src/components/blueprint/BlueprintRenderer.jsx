// frontend/src/components/blueprint/BlueprintRenderer.jsx
import React from 'react';
import { computeViewBox } from './utils/coordinateTransform';
import { 
  RoomLayer, WallLayer, DoorLayer, WindowLayer, LabelLayer, 
  StructuralLayer, FixtureLayer, FurnitureLayer, DimensionLayer, AnnotationLayer 
} from './layers';
import LayerErrorBoundary from './LayerErrorBoundary';

export default function BlueprintRenderer({ 
  schema, 
  layersVisibility = {}
}) {
  if (!schema || !schema.metadata) {
    return (
      <div className="flex items-center justify-center h-full w-full text-secondary/40 font-light">
        No blueprint data loaded
      </div>
    );
  }

  const viewBox = computeViewBox(schema);

  // Default visibility flags if not provided
  const visibility = {
    rooms: true,
    walls: true,
    doors: true,
    windows: true,
    labels: true,
    structural: true,
    fixtures: true,
    furniture: true,
    dimensions: true,
    annotations: true,
    ...layersVisibility
  };

  return (
    <svg 
      id="blueprint-canvas-svg"
      viewBox={viewBox} 
      className="w-full h-full select-none"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        backgroundColor: "#ffffff",
        boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)"
      }}
    >
      <defs>
        {/* Master Wall diagonal hatch pattern */}
        <pattern id="wall-hatch" width="4" height="4" patternUnits="userSpaceOnUse">
          <line x1="0" y1="4" x2="4" y2="0" stroke="#555555" strokeWidth="0.4" />
        </pattern>
      </defs>

      {/* Layer 1: Pastel Room Polygons */}
      <LayerErrorBoundary layerName="rooms">
        <RoomLayer 
          rooms={schema.rooms} 
          unitSystem={schema.metadata?.unit_system} 
          visible={visibility.rooms} 
        />
      </LayerErrorBoundary>

      {/* Layer 2: Fixtures (WC, Washbasin, Kitchen Counter) */}
      <LayerErrorBoundary layerName="fixtures">
        <FixtureLayer 
          fixtures={schema.fixtures || []} 
          visible={visibility.fixtures} 
        />
      </LayerErrorBoundary>

      {/* Layer 3: Furnishings */}
      <LayerErrorBoundary layerName="furniture">
        <FurnitureLayer 
          furniture={schema.furniture || []} 
          visible={visibility.furniture} 
        />
      </LayerErrorBoundary>

      {/* Layer 4: Master Wall Boundary Path */}
      <LayerErrorBoundary layerName="walls">
        <WallLayer 
          walls={schema.walls} 
          visible={visibility.walls} 
        />
      </LayerErrorBoundary>

      {/* Layer 5: Openings (Doors and Windows) */}
      <LayerErrorBoundary layerName="doors">
        <DoorLayer 
          doors={schema.doors || []} 
          visible={visibility.doors} 
        />
      </LayerErrorBoundary>
      <LayerErrorBoundary layerName="windows">
        <WindowLayer 
          windows={schema.windows || []} 
          visible={visibility.windows} 
        />
      </LayerErrorBoundary>

      {/* Layer 6: Structural RCC frame */}
      <LayerErrorBoundary layerName="structural">
        <StructuralLayer 
          structural={schema.structural} 
          visible={visibility.structural} 
        />
      </LayerErrorBoundary>

      {/* Layer 7: Text Labels (Room Name + dimensions) */}
      <LayerErrorBoundary layerName="labels">
        <LabelLayer 
          rooms={schema.rooms} 
          unitSystem={schema.metadata?.unit_system} 
          visible={visibility.labels} 
        />
      </LayerErrorBoundary>

      {/* Layer 8: Exterior CAD dimension chains */}
      <LayerErrorBoundary layerName="dimensions">
        <DimensionLayer 
          dimensionChains={schema.dimension_chains} 
          visible={visibility.dimensions} 
        />
      </LayerErrorBoundary>

      {/* Layer 9: Legend, Compass, North Arrow, and Title block */}
      <LayerErrorBoundary layerName="annotations">
        <AnnotationLayer 
          schema={schema} 
          visible={visibility.annotations} 
        />
      </LayerErrorBoundary>
    </svg>
  );
}
