"use client";

import { Filters } from "@/hooks/useTenders";
import { CATEGORIES, CATEGORY_COLORS } from "@/lib/constants";
import { TenderCategory } from "@/lib/types";

interface Props {
  filters: Filters;
  setFilters: (f: Filters) => void;
  availableStates: string[];
  activeTotalCount: number;
  filteredCount: number;
}

export default function FilterBar({
  filters,
  setFilters,
  availableStates,
  activeTotalCount,
  filteredCount,
}: Props) {
  function toggleCategory(cat: TenderCategory) {
    const next = filters.categories.includes(cat)
      ? filters.categories.filter((c) => c !== cat)
      : [...filters.categories, cat];
    setFilters({ ...filters, categories: next });
  }

  return (
    <div className="p-3 border-b border-slate-700 space-y-3">
      {/* Search */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search tenders…"
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          className="w-full bg-slate-700/60 border border-slate-600 rounded-md px-3 py-1.5 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
        />
        {filters.search && (
          <button
            onClick={() => setFilters({ ...filters, search: "" })}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs"
          >
            ✕
          </button>
        )}
      </div>

      {/* Category chips */}
      <div className="flex flex-wrap gap-1.5">
        {CATEGORIES.map((cat) => {
          const active = filters.categories.includes(cat);
          const color = CATEGORY_COLORS[cat];
          return (
            <button
              key={cat}
              onClick={() => toggleCategory(cat)}
              className="text-[10px] px-2 py-0.5 rounded-full border transition-all font-medium"
              style={{
                borderColor: active ? color : "#334155",
                backgroundColor: active ? `${color}33` : "transparent",
                color: active ? color : "#94a3b8",
              }}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {/* State dropdown */}
      <select
        value={filters.states[0] ?? ""}
        onChange={(e) =>
          setFilters({ ...filters, states: e.target.value ? [e.target.value] : [] })
        }
        className="w-full bg-slate-700/60 border border-slate-600 rounded-md px-2 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500"
      >
        <option value="">All states</option>
        {availableStates.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      {/* Count + show closed toggle */}
      <div className="flex items-center justify-between">
        <p className="text-[10px] text-slate-500">
          {filteredCount} of {activeTotalCount} active tenders
        </p>
        <button
          onClick={() => setFilters({ ...filters, showClosed: !filters.showClosed })}
          className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border transition-all ${
            filters.showClosed
              ? "border-slate-500 bg-slate-700 text-slate-300"
              : "border-slate-700 text-slate-600 hover:text-slate-400"
          }`}
        >
          <span>{filters.showClosed ? "✓" : ""} Show closed</span>
        </button>
      </div>
    </div>
  );
}
