export function formatValue(raw: string | undefined): string {
  if (!raw || raw.trim() === "" || raw.toUpperCase() === "NA") return "N/A";
  const num = parseFloat(raw.replace(/,/g, "").replace(/[^\d.]/g, ""));
  if (isNaN(num) || num === 0) return "N/A";
  if (num >= 1e7) return `₹${(num / 1e7).toFixed(1)} Cr`;
  if (num >= 1e5) return `₹${(num / 1e5).toFixed(1)} L`;
  return `₹${num.toLocaleString("en-IN")}`;
}

/** Returns true if city looks like a real place (not a highway ref or km marker). */
export function isRealCity(city: string | undefined): boolean {
  if (!city || city.trim().length < 3) return false;
  return !/^(nh|sh|mh|rnh)\s*[\-\d]/i.test(city) &&
         !/^\d/.test(city) &&
         !/\bkm\b/i.test(city);
}

export function formatDate(raw: string): string {
  if (!raw) return "—";
  // Strip any trailing time portion ("05:30 PM", "17:30:00", etc.)
  const dateOnly = raw.replace(/\s+\d{1,2}:\d{2}(:\d{2})?(\s*(AM|PM))?$/i, "").trim();
  return dateOnly.replace(/-/g, "/");
}

const MONTHS: Record<string, number> = {
  Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5,
  Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11,
};

/**
 * Parse eprocure closing date strings like "17-Jun-2026" or "17/Jun/2026".
 * Returns a Date set to midnight local time, or null if unparseable.
 */
export function parseClosingDate(raw: string | undefined): Date | null {
  if (!raw) return null;
  const m = raw.match(/(\d{1,2})[-/]([A-Za-z]{3})[-/](\d{4})/);
  if (!m) return null;
  const month = MONTHS[m[2]];
  if (month === undefined) return null;
  return new Date(parseInt(m[3]), month, parseInt(m[1]));
}

/** True if the tender's closing date is strictly in the past. */
export function isPastClosing(raw: string | undefined): boolean {
  const d = parseClosingDate(raw);
  if (!d) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d < today;
}
