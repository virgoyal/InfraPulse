"use client";

import { useState, useEffect } from "react";
import { InsightsData } from "@/lib/types";

export function useInsights() {
  const [insights, setInsights] = useState<InsightsData>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/data/insights.json")
      .then((r) => r.json())
      .then((data: InsightsData) => {
        setInsights(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return { insights, loading };
}
