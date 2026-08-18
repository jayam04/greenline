export type TimelineKey = 
  | "THIS_WEEK"
  | "LAST_WEEK"
  | "THIS_MONTH"
  | "LAST_MONTH"
  | "1M"
  | "1Y"
  | "YTD"
  | "ALL";

export interface TimelineOption {
  key: TimelineKey;
  label: string;
}

export const TIMELINE_OPTIONS: TimelineOption[] = [
  { key: "THIS_WEEK", label: "This Week" },
  { key: "LAST_WEEK", label: "Last Week" },
  { key: "THIS_MONTH", label: "This Month" },
  { key: "LAST_MONTH", label: "Last Month" },
  { key: "1M", label: "1M" },
  { key: "1Y", label: "1Y" },
  { key: "YTD", label: "YTD" },
  { key: "ALL", label: "All Time" },
];

export function getTimelineDateRange(key: TimelineKey): { startDate?: string; endDate?: string } {
  const today = new Date();
  const formatDate = (d: Date) => d.toISOString().split("T")[0];

  switch (key) {
    case "THIS_WEEK": {
      // Monday of current week
      const d = new Date(today);
      const day = d.getDay(); // 0 is Sunday, 1 is Monday
      const diff = d.getDate() - day + (day === 0 ? -6 : 1);
      const monday = new Date(d.setDate(diff));
      return { startDate: formatDate(monday), endDate: formatDate(today) };
    }
    case "LAST_WEEK": {
      // Monday of last week to Sunday of last week
      const d = new Date(today);
      const day = d.getDay();
      const diff = d.getDate() - day + (day === 0 ? -6 : 1) - 7;
      const lastMonday = new Date(d.setDate(diff));
      const lastSunday = new Date(lastMonday);
      lastSunday.setDate(lastMonday.getDate() + 6);
      return { startDate: formatDate(lastMonday), endDate: formatDate(lastSunday) };
    }
    case "THIS_MONTH": {
      const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
      return { startDate: formatDate(firstDay), endDate: formatDate(today) };
    }
    case "LAST_MONTH": {
      const firstDayLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const lastDayLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
      return { startDate: formatDate(firstDayLastMonth), endDate: formatDate(lastDayLastMonth) };
    }
    case "1M": {
      const d = new Date(today);
      d.setDate(d.getDate() - 30);
      return { startDate: formatDate(d), endDate: formatDate(today) };
    }
    case "1Y": {
      const d = new Date(today);
      d.setFullYear(d.getFullYear() - 1);
      return { startDate: formatDate(d), endDate: formatDate(today) };
    }
    case "YTD": {
      const firstDayYear = new Date(today.getFullYear(), 0, 1);
      return { startDate: formatDate(firstDayYear), endDate: formatDate(today) };
    }
    case "ALL":
    default:
      return {};
  }
}
