"use client";

import { useRef, useEffect } from "react";
import { GeoJSON, useMap } from "react-leaflet";
import L from "leaflet";
import { Tender } from "@/lib/types";

// GeoJSON NAME_1 → our canonical state names
const NAME_FIXES: Record<string, string> = {
  Orissa: "Odisha",
  Uttaranchal: "Uttarakhand",
  "Jammu & Kashmir": "Jammu and Kashmir",
  Pondicherry: "Puducherry",
};

// 5-bucket color scale by tender count
function getColor(count: number): string {
  if (count === 0) return "#1e293b";
  if (count <= 5) return "#1d4ed8";
  if (count <= 15) return "#7c3aed";
  if (count <= 30) return "#be185d";
  return "#dc2626";
}

function getStyle(
  feature: GeoJSON.Feature | undefined,
  counts: Record<string, number>,
  selectedState: string | null
): L.PathOptions {
  const rawName = (feature?.properties as Record<string, string>)?.NAME_1 ?? "";
  const stateName = NAME_FIXES[rawName] ?? rawName;
  const count = counts[stateName] ?? 0;
  const isSelected = stateName === selectedState;

  return {
    fillColor: getColor(count),
    fillOpacity: isSelected ? 0.7 : count > 0 ? 0.35 : 0.08,
    color: isSelected ? "#e2e8f0" : "#475569",
    weight: isSelected ? 2 : 0.8,
  };
}

interface Props {
  geojson: object;
  allTenders: Tender[];
  selectedState: string | null;
  onStateClick: (state: string) => void;
}

export default function StateLayer({ geojson, allTenders, selectedState, onStateClick }: Props) {
  const geojsonRef = useRef<L.GeoJSON | null>(null);

  // Build counts from ALL tenders (not filtered)
  const counts: Record<string, number> = {};
  for (const t of allTenders) {
    counts[t.state] = (counts[t.state] ?? 0) + 1;
  }

  // Re-apply styles when selectedState changes without remounting
  useEffect(() => {
    const layer = geojsonRef.current;
    if (!layer) return;
    layer.eachLayer((l) => {
      const feature = (l as L.Path & { feature?: GeoJSON.Feature }).feature;
      (l as L.Path).setStyle(getStyle(feature, counts, selectedState));
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedState]);

  const onEachFeature = (feature: GeoJSON.Feature, layer: L.Layer) => {
    const rawName = (feature.properties as Record<string, string>)?.NAME_1 ?? "";
    const stateName = NAME_FIXES[rawName] ?? rawName;
    const count = counts[stateName] ?? 0;

    // Tooltip showing state name + tender count
    (layer as L.Path).bindTooltip(
      `<strong>${stateName}</strong><br/>${count} tender${count !== 1 ? "s" : ""}`,
      { sticky: true, className: "state-tooltip" }
    );

    layer.on({
      mouseover(e) {
        const target = e.target as L.Path;
        const base = getStyle(feature, counts, selectedState);
        target.setStyle({
          ...base,
          fillOpacity: Math.min((base.fillOpacity as number) + 0.2, 0.85),
        });
      },
      mouseout(e) {
        const target = e.target as L.Path;
        target.setStyle(getStyle(feature, counts, selectedState));
      },
      click() {
        onStateClick(stateName);
      },
    });
  };

  return (
    <GeoJSON
      ref={geojsonRef}
      data={geojson as GeoJSON.GeoJsonObject}
      style={(feature) => getStyle(feature, counts, selectedState)}
      onEachFeature={onEachFeature}
      pane="statePane"
    />
  );
}
