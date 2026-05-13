import { TenderCategory } from "@/lib/types";
import { CATEGORY_COLORS } from "@/lib/constants";

export default function Badge({ category }: { category: TenderCategory }) {
  const color = CATEGORY_COLORS[category] ?? "#94a3b8";
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide"
      style={{ backgroundColor: `${color}22`, color }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
      {category}
    </span>
  );
}
