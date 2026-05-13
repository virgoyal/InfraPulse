"use client";

import { useInsights } from "@/hooks/useInsights";
import { CATEGORY_COLORS } from "@/lib/constants";
import { TenderCategory } from "@/lib/types";

interface Props {
  activeState?: string;
}

export default function InsightsPanel({ activeState }: Props) {
  const { insights, loading } = useInsights();

  if (loading) {
    return (
      <div className="h-44 bg-slate-900 border-t border-slate-700 flex items-center justify-center">
        <p className="text-slate-500 text-sm">Loading insights…</p>
      </div>
    );
  }

  const states = Object.keys(insights);
  if (!states.length) {
    return (
      <div className="h-44 bg-slate-900 border-t border-slate-700 flex items-center justify-center">
        <p className="text-slate-500 text-sm">No insights yet — run the pipeline first.</p>
      </div>
    );
  }

  // Show active state insight prominently, then others
  const ordered = activeState && insights[activeState]
    ? [activeState, ...states.filter((s) => s !== activeState)]
    : states;

  return (
    <div className="border-t border-slate-700 bg-slate-900">
      <div className="px-4 py-2 border-b border-slate-800">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
          Regional Insights
        </h2>
      </div>
      <div className="flex gap-3 overflow-x-auto px-3 py-3 h-52 scrollbar-thin scrollbar-thumb-slate-700">
        {ordered.map((state) => {
          const insight = insights[state];
          const isActive = state === activeState;
          return (
            <div
              key={state}
              className={`flex-shrink-0 w-72 rounded-lg border p-3 transition-all flex flex-col ${
                isActive
                  ? "border-blue-500 bg-slate-800"
                  : "border-slate-700 bg-slate-800/50"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-semibold text-white">{state}</span>
                <span className="text-[10px] text-slate-500">
                  {insight.tender_count} tenders
                </span>
              </div>
              <div className="flex-1 overflow-y-auto max-h-28 scrollbar-thin scrollbar-thumb-slate-600 pr-0.5">
                <p className="text-xs text-slate-300 leading-relaxed">
                  {insight.text}
                </p>
              </div>
              {insight.top_categories?.length > 0 && (
                <div className="flex gap-1 mt-2 flex-wrap">
                  {insight.top_categories.map((cat) => {
                    const color = CATEGORY_COLORS[cat as TenderCategory] ?? "#94a3b8";
                    return (
                      <span
                        key={cat}
                        className="text-[9px] px-1.5 py-0.5 rounded-full font-medium"
                        style={{ backgroundColor: `${color}22`, color }}
                      >
                        {cat}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
