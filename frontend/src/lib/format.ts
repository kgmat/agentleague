export const fmtTime = (ts: number | string) => {
  const d = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
  return d.toLocaleTimeString();
};

export const fmtDate = (s: string) => new Date(s).toLocaleString();

export const fmtCost = (n: number) => `$${n.toFixed(n < 0.01 ? 5 : 2)}`;

export const statusBadge = (status: string): string => {
  switch (status) {
    case "completed":
      return "green";
    case "running":
    case "pending":
      return "amber";
    case "failed":
      return "red";
    default:
      return "gray";
  }
};
