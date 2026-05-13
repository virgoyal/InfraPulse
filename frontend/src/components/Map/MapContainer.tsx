"use client";

import dynamic from "next/dynamic";
import { Tender } from "@/lib/types";
import MapLegend from "./MapLegend";

// Leaflet uses `window` at import time — must disable SSR
const IndiaMap = dynamic(() => import("./IndiaMap"), {
  ssr: false,
  loading: () => (
    <div className="h-full bg-slate-800 flex items-center justify-center text-slate-400 text-sm">
      Loading map…
    </div>
  ),
});

interface Props {
  tenders: Tender[];
  allTenders: Tender[];
  selected: Tender | null;
  onSelect: (t: Tender | null) => void;
  selectedState: string | null;
  onStateClick: (state: string) => void;
}

export default function MapContainer({
  tenders,
  allTenders,
  selected,
  onSelect,
  selectedState,
  onStateClick,
}: Props) {
  return (
    <div className="h-full relative">
      <IndiaMap
        tenders={tenders}
        allTenders={allTenders}
        selected={selected}
        onSelect={onSelect}
        selectedState={selectedState}
        onStateClick={onStateClick}
      />
      <div className="absolute bottom-6 right-4 z-[1000] pointer-events-none">
        <MapLegend />
      </div>
    </div>
  );
}
