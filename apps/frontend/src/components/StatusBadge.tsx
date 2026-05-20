import { Badge } from "./ui";

export function StatusBadge({ status }: { status?: string }) {
  const s = status || "unknown";
  const tone = s.includes("FAILED") ? "red" : s.includes("COMPLETED") ? "green" : s.includes("WAITING") ? "yellow" : "neutral";
  return <Badge tone={tone}>{s}</Badge>;
}

