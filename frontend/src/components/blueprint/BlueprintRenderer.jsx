// frontend/src/components/blueprint/BlueprintRenderer.jsx
import React from 'react';
import { computeViewBox } from './utils/coordinateTransform';
import { 
  RoomLayer, WallLayer, DoorLayer, WindowLayer, LabelLayer, 
  StructuralLayer, FixtureLayer, FurnitureLayer, DimensionLayer, AnnotationLayer 
} from './layers';

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
      <RoomLayer 
        rooms={schema.rooms} 
        unitSystem={schema.metadata.unit_system} 
        visible={visibility.rooms} 
      />

      {/* Layer 2: Fixtures (WC, Washbasin, Kitchen Counter) */}
      <FixtureLayer 
        fixtures={schema.fixtures || []} 
        visible={visibility.fixtures} 
      />

      {/* Layer 3: Furnishings */}
      <FurnitureLayer 
        furniture={schema.furniture || []} 
        visible={visibility.furniture} 
      />

      {/* Layer 4: Master Wall Boundary Path */}
      <WallLayer 
        walls={schema.walls} 
        visible={visibility.walls} 
      />

      {/* Layer 5: Openings (Doors and Windows) */}
      <DoorLayer 
        doors={schema.doors || []} 
        visible={visibility.doors} 
      />
      <WindowLayer 
        windows={schema.windows || []} 
        visible={visibility.windows} 
      />

      {/* Layer 6: Structural RCC frame */}
      <StructuralLayer 
        structural={schema.structural} 
        visible={visibility.structural} 
      />

      {/* Layer 7: Text Labels (Room Name + dimensions) */}
      <LabelLayer 
        rooms={schema.rooms} 
        unitSystem={schema.metadata.unit_system} 
        visible={visibility.labels} 
      />

      {/* Layer 8: Exterior CAD dimension chains */}
      <DimensionLayer 
        dimensionChains={schema.dimension_chains} 
        visible={visibility.dimensions} 
      />

      {/* Layer 9: Legend, Compass, North Arrow, and Title block */}
      <AnnotationLayer 
        schema={schema} 
        visible={visibility.annotations} 
      />
    </svg>
  );
}
