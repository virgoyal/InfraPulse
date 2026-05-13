"use client";

import { useCallback } from "react";
import { useTenders } from "@/hooks/useTenders";
import Sidebar from "@/components/Sidebar/Sidebar";
import MapContainer from "@/components/Map/MapContainer";
import InsightsPanel from "@/components/InsightsPanel/InsightsPanel";

export default function Home() {
  const {
    tenders,
    allTenders,
    activeTotalCount,
    loading,
    filters,
    setFilters,
    availableStates,
    selected,
    setSelected,
  } = useTenders();

  // Toggle state filter when a choropleth polygon is clicked
  const handleStateClick = useCallback(
    (state: string) => {
      setFilters((prev) => {
        const already = prev.states.includes(state);
        return { ...prev, states: already ? [] : [state] };
      });
    },
    [setFilters]
  );

  // The currently active state filter (single value or null)
  const selectedState = filters.states.length === 1 ? filters.states[0] : null;

  return (
    <div className="flex h-screen bg-slate-950 overflow-hidden">
      <Sidebar
        tenders={tenders}
        allTenders={allTenders}
        activeTotalCount={activeTotalCount}
        loading={loading}
        filters={filters}
        setFilters={setFilters}
        availableStates={availableStates}
        selected={selected}
        onSelect={setSelected}
      />

      <main className="flex-1 flex flex-col min-w-0 relative">
        <div className="flex-1 relative min-h-0">
          <MapContainer
            tenders={tenders}
            allTenders={allTenders}
            selected={selected}
            onSelect={setSelected}
            selectedState={selectedState}
            onStateClick={handleStateClick}
          />
        </div>
        <InsightsPanel activeState={selected?.state ?? selectedState ?? undefined} />
      </main>
    </div>
  );
}
