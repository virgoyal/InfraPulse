"use client";

import { CATEGORIES, CATEGORY_COLORS } from "@/lib/constants";

const CHOROPLETH_BUCKETS = [
  { label: "No tenders", color: "#1e293b" },
  { label: "1–5", color: "#1d4ed8" },
  { label: "6–15", color: "#7c3aed" },
  { label: "16–30", color: "#be185d" },
  { label: "31+", color: "#dc2626" },
];

export default function MapLegend() {
  return (
    <div className="bg-slate-900/90 border border-slate-700 rounded-lg px-3 py-2 text-xs space-y-3">
      {/* Category dots */}
      <div>
        <p className="text-slate-400 font-medium mb-1">Category</p>
        <div className="space-y-1">
          {CATEGORIES.map((cat) => (
            <div key={cat} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block flex-shrink-0"
                style={{ backgroundColor: CATEGORY_COLORS[cat] }}
              />
              <span className="text-slate-300">{cat}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-slate-700" />

      {/* State tender count */}
      <div>
        <p className="text-slate-400 font-medium mb-1">Tenders per state</p>
        <div className="space-y-1">
          {CHOROPLETH_BUCKETS.map(({ label, color }) => (
            <div key={label} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-sm inline-block flex-shrink-0"
                style={{ backgroundColor: color, opacity: 0.7 }}
              />
              <span className="text-slate-300">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
