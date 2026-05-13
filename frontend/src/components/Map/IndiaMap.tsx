"use client";

import { useEffect, useState, useCallback } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { Tender } from "@/lib/types";
import { CATEGORY_COLORS, INDIA_CENTER, INDIA_DEFAULT_ZOOM } from "@/lib/constants";
import { formatValue, formatDate, isRealCity } from "@/lib/formatters";
import Badge from "@/components/shared/Badge";
import StateLayer from "./StateLayer";

interface Props {
  tenders: Tender[];
  allTenders: Tender[];
  selected: Tender | null;
  onSelect: (t: Tender | null) => void;
  selectedState: string | null;
  onStateClick: (state: string) => void;
}

/**
 * Copies the tender ID to clipboard. eProcure detail URLs contain session tokens
 * that expire within minutes, so there is no stable permalink — the tender ID is
 * the canonical reference users can paste into eprocure's search.
 */
function CopyButton({ tenderId }: { tenderId: string }) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(() => {
    navigator.clipboard.writeText(tenderId).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [tenderId]);

  return (
    <button
      onClick={copy}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        marginTop: 8,
        padding: "3px 10px",
        fontSize: 11,
        borderRadius: 4,
        border: "1px solid #334155",
        background: copied ? "#166534" : "#1e3a5f",
        color: copied ? "#86efac" : "#93c5fd",
        cursor: "pointer",
        transition: "all 0.15s",
      }}
    >
      {copied ? "✓ Copied!" : "Copy Tender ID"}
    </button>
  );
}

function FlyToSelected({ tender }: { tender: Tender | null }) {
  const map = useMap();
  useEffect(() => {
    if (tender) {
      map.flyTo(tender.coordinates, Math.max(map.getZoom(), 7), { duration: 0.8 });
    }
  }, [tender, map]);
  return null;
}

/**
 * Creates a custom Leaflet pane at z-index 300 (below the default overlayPane at 400).
 * State polygons are rendered here so circle markers always receive clicks first.
 */
function CreateStatePane() {
  const map = useMap();
  useEffect(() => {
    if (!map.getPane("statePane")) {
      const pane = map.createPane("statePane");
      pane.style.zIndex = "300";
    }
  }, [map]);
  return null;
}

export default function IndiaMap({
  tenders,
  allTenders,
  selected,
  onSelect,
  selectedState,
  onStateClick,
}: Props) {
  const [geojson, setGeojson] = useState<object | null>(null);

  useEffect(() => {
    fetch("/data/india-states.geojson")
      .then((r) => r.json())
      .then(setGeojson)
      .catch(() => {/* choropleth optional — fail silently */});
  }, []);

  return (
    <MapContainer
      center={INDIA_CENTER}
      zoom={INDIA_DEFAULT_ZOOM}
      minZoom={4}
      maxZoom={12}
      style={{ height: "100%", width: "100%" }}
      className="z-0"
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
      />

      <CreateStatePane />

      {/* Choropleth layer — rendered in statePane (z-index 300) so dots always get clicks */}
      {geojson && (
        <StateLayer
          geojson={geojson}
          allTenders={allTenders}
          selectedState={selectedState}
          onStateClick={onStateClick}
        />
      )}

      {tenders.map((tender) => {
        const color = CATEGORY_COLORS[tender.category] ?? "#94a3b8";
        const isSelected = selected?.tender_id === tender.tender_id;
        const value = formatValue(tender.value);
        const city = isRealCity(tender.location_city) ? tender.location_city : null;
        const locationStr = [city, tender.state].filter(Boolean).join(", ");

        return (
          <CircleMarker
            key={tender.tender_id}
            center={tender.coordinates}
            radius={isSelected ? 10 : 6}
            pathOptions={{
              color: isSelected ? "#ffffff" : color,
              fillColor: color,
              fillOpacity: isSelected ? 1 : 0.75,
              weight: isSelected ? 2.5 : 1,
            }}
            eventHandlers={{ click: () => onSelect(isSelected ? null : tender) }}
          >
            <Popup minWidth={220} maxWidth={300}>
              <div style={{ fontFamily: "inherit", padding: "2px 0" }}>
                {/* Top row: badge + value */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
                  <Badge category={tender.category} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: value === "N/A" ? "#64748b" : "#34d399" }}>
                    {value}
                  </span>
                </div>

                {/* AI summary — always shown as the clean headline */}
                {tender.summary && (
                  <p style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.45, color: "#f1f5f9", marginBottom: 8 }}>
                    {tender.summary}
                  </p>
                )}

                {/* Tender ID */}
                <p style={{ fontSize: 10, color: "#94a3b8", fontFamily: "monospace", marginBottom: 6 }}>
                  <span style={{ fontFamily: "inherit" }}>Tender ID: </span>
                  {tender.tender_id}
                </p>

                {/* Location */}
                <p style={{ fontSize: 11, color: "#94a3b8", marginBottom: 3 }}>
                  📍 {locationStr}
                </p>

                {/* Duration + closing date */}
                {(tender.period_of_work || tender.closing_date) && (
                  <p style={{ fontSize: 11, color: "#64748b" }}>
                    {tender.period_of_work && <span>⏱ {tender.period_of_work} days</span>}
                    {tender.period_of_work && tender.closing_date && <span style={{ margin: "0 4px" }}>·</span>}
                    {tender.closing_date && <span>Closes {formatDate(tender.closing_date)}</span>}
                  </p>
                )}

                {/* Copy tender ID — direct links to eprocure expire (session tokens) */}
                <CopyButton tenderId={tender.tender_id} />
              </div>
            </Popup>
          </CircleMarker>
        );
      })}

      <FlyToSelected tender={selected} />
    </MapContainer>
  );
}
