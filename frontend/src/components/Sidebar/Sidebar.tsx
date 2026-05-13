"use client";

import { Tender } from "@/lib/types";
import { Filters } from "@/hooks/useTenders";
import FilterBar from "./FilterBar";
import TenderCard from "./TenderCard";

interface Props {
  tenders: Tender[];
  allTenders: Tender[];
  activeTotalCount: number;
  loading: boolean;
  filters: Filters;
  setFilters: (f: Filters) => void;
  availableStates: string[];
  selected: Tender | null;
  onSelect: (t: Tender | null) => void;
}

export default function Sidebar({
  tenders,
  allTenders,
  activeTotalCount,
  loading,
  filters,
  setFilters,
  availableStates,
  selected,
  onSelect,
}: Props) {
  return (
    <aside className="w-80 flex-shrink-0 bg-slate-900 border-r border-slate-700 flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700">
        <h1 className="text-lg font-bold text-white tracking-tight">InfraPulse</h1>
        <p className="text-[11px] text-slate-400 mt-0.5">
          India infrastructure tender intelligence
        </p>
      </div>

      <FilterBar
        filters={filters}
        setFilters={setFilters}
        availableStates={availableStates}
        activeTotalCount={activeTotalCount}
        filteredCount={tenders.length}
      />

      {/* Tender list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {loading ? (
          <div className="space-y-2 p-1">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-20 bg-slate-800 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : tenders.length === 0 ? (
          <p className="text-slate-500 text-sm text-center mt-10">No tenders match filters.</p>
        ) : (
          tenders.map((t) => (
            <TenderCard
              key={t.tender_id}
              tender={t}
              isSelected={selected?.tender_id === t.tender_id}
              onClick={() => onSelect(selected?.tender_id === t.tender_id ? null : t)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
