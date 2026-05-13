export type TenderCategory =
  | "Bridge"
  | "Road Expansion"
  | "Maintenance"
  | "Drainage"
  | "Flood Mitigation"
  | "Consultancy"
  | "Safety";

export interface Tender {
  tender_id: string;
  title: string;
  organization: string;
  state: string;
  coordinates: [number, number]; // [lat, lng]
  value: string;
  category: TenderCategory;
  summary: string;
  fiscal_year: string;
  published_date: string;
  closing_date: string;
  detail_url: string;
  status?: "active" | "archived"; // "archived" = no longer on eprocure listing
  // Detail page fields
  work_description?: string;
  location_city?: string;
  period_of_work?: string;
  product_category?: string;
  contract_type?: string;
  geo_source?: string;
}

export interface StateInsight {
  text: string;
  tender_count: number;
  total_value_crore: number;
  top_categories: string[];
}

export type InsightsData = Record<string, StateInsight>;
