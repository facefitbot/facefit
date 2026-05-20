import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { Card, SectionTitle } from "../components/ui";

export function Reports() {
  const { data } = useQuery({ queryKey: ["reports-analysis"], queryFn: () => apiRequest<any>("/api/analysis") });
  const items = (data?.items || []).filter((item: any) => item.report_token);
  return (
    <div>
      <SectionTitle title="Отчеты" subtitle="Публичные ссылки и статус готовности" />
      <div className="grid gap-4">
        {items.map((item: any) => (
          <Card key={item.id} className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-bold">Отчет анализа #{item.id} · {item.lead?.name || "Без имени"}</p>
              <p className="text-sm text-clay">/report/{item.report_token}</p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={item.status} />
              <Link to={`/report/${item.report_token}`} target="_blank" className="inline-flex items-center gap-2 text-sm font-semibold text-rose">
                <ExternalLink size={16} /> Открыть
              </Link>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

