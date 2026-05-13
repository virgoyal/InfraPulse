import { TenderCategory } from "./types";

export const CATEGORY_COLORS: Record<TenderCategory, string> = {
  Bridge: "#EF4444",
  "Road Expansion": "#F97316",
  Maintenance: "#EAB308",
  Drainage: "#3B82F6",
  "Flood Mitigation": "#06B6D4",
  Consultancy: "#8B5CF6",
  Safety: "#22C55E",
};

export const CATEGORIES: TenderCategory[] = [
  "Bridge",
  "Road Expansion",
  "Maintenance",
  "Drainage",
  "Flood Mitigation",
  "Consultancy",
  "Safety",
];

export const INDIA_CENTER: [number, number] = [22.5937, 78.9629];
export const INDIA_DEFAULT_ZOOM = 5;
