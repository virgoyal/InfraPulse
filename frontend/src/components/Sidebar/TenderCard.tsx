import { Tender } from "@/lib/types";
import Badge from "@/components/shared/Badge";
import { formatValue, formatDate, isRealCity, isPastClosing } from "@/lib/formatters";

interface Props {
  tender: Tender;
  isSelected: boolean;
  onClick: () => void;
}

export default function TenderCard({ tender, isSelected, onClick }: Props) {
  const city = isRealCity(tender.location_city) ? tender.location_city : null;
  const value = formatValue(tender.value);
  const archived = tender.status === "archived";
  const pastClosing = !archived && isPastClosing(tender.closing_date);
  const isDimmed = archived || pastClosing;

  // Closing date label
  const closingLabel = archived
    ? `Closed ${formatDate(tender.closing_date)}`
    : pastClosing
    ? `Closed ${formatDate(tender.closing_date)}`
    : `Closes ${formatDate(tender.closing_date)}`;

  const closingColor = archived || pastClosing ? "text-amber-700" : "text-slate-500";

  return (
    <div
      onClick={onClick}
      className={`p-3 rounded-lg cursor-pointer border transition-all ${
        isDimmed ? "opacity-50" : ""
      } ${
        isSelected
          ? "border-blue-500 bg-slate-700/60"
          : "border-slate-700/50 bg-slate-800/60 hover:border-slate-500 hover:bg-slate-700/40"
      }`}
    >
      {/* Status tag for archived / closed */}
      {(archived || pastClosing) && (
        <div className="mb-1.5">
          <span className={`text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded ${
            archived
              ? "bg-slate-700 text-slate-400"
              : "bg-amber-950/60 text-amber-600"
          }`}>
            {archived ? "Archived" : "Closed"}
          </span>
        </div>
      )}

      {/* Top row: badge + value */}
      <div className="flex items-center justify-between gap-2">
        <Badge category={tender.category} />
        <span className={`text-xs font-semibold ${value === "N/A" ? "text-slate-500" : "text-emerald-400"}`}>
          {value}
        </span>
      </div>

      {/* Heading: AI summary in italic (preferred) or raw title truncated to 1 line */}
      {tender.summary ? (
        <p className="text-sm italic mt-2 leading-snug line-clamp-2 text-slate-200">
          {tender.summary}
        </p>
      ) : (
        <p className="text-xs mt-2 leading-snug line-clamp-2 text-slate-400">
          {tender.title}
        </p>
      )}

      {/* Tender ID */}
      <p className="text-[9px] font-mono text-slate-600 mt-1 truncate">
        {tender.tender_id}
      </p>

      {/* Location row */}
      <div className="flex items-center gap-1.5 mt-1.5 text-xs text-slate-400">
        <span>📍</span>
        <span>{[city, tender.state].filter(Boolean).join(", ")}</span>
      </div>

      {/* Footer: duration + closing date */}
      <div className="flex items-center justify-between mt-2 text-[10px] text-slate-500">
        {tender.period_of_work && (
          <span>⏱ {tender.period_of_work} days</span>
        )}
        {tender.closing_date && (
          <span className={closingColor}>{closingLabel}</span>
        )}
      </div>
    </div>
  );
}
