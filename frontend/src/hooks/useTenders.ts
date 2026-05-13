"use client";

import { useState, useEffect, useMemo } from "react";
import { Tender, TenderCategory } from "@/lib/types";
import { isPastClosing } from "@/lib/formatters";

export interface Filters {
  categories: TenderCategory[];
  states: string[];
  search: string;
  showClosed: boolean; // includes past-closing-date + archived tenders
}

const EMPTY_FILTERS: Filters = {
  categories: [],
  states: [],
  search: "",
  showClosed: false,
};

export function useTenders() {
  const [allTenders, setAllTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selected, setSelected] = useState<Tender | null>(null);

  useEffect(() => {
    fetch("/data/tenders.json")
      .then((r) => r.json())
      .then((data: Tender[]) => {
        setAllTenders(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const tenders = useMemo(() => {
    return allTenders.filter((t) => {
      // Hide archived tenders unless showClosed
      if (!filters.showClosed && t.status === "archived") return false;

      // Hide past-closing-date tenders unless showClosed
      if (!filters.showClosed && isPastClosing(t.closing_date)) return false;

      if (filters.categories.length && !filters.categories.includes(t.category))
        return false;
      if (filters.states.length && !filters.states.includes(t.state))
        return false;
      if (filters.search) {
        const q = filters.search.toLowerCase();
        return (
          t.title.toLowerCase().includes(q) ||
          t.organization.toLowerCase().includes(q) ||
          t.state.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [allTenders, filters]);

  // Count of active (non-closed, non-archived) tenders for the header
  const activeTotalCount = useMemo(
    () =>
      allTenders.filter(
        (t) => t.status !== "archived" && !isPastClosing(t.closing_date)
      ).length,
    [allTenders]
  );

  const availableStates = useMemo(
    () => Array.from(new Set(allTenders.map((t) => t.state))).sort(),
    [allTenders]
  );

  return {
    tenders,
    allTenders,
    activeTotalCount,
    loading,
    filters,
    setFilters,
    selected,
    setSelected,
    availableStates,
  };
}
