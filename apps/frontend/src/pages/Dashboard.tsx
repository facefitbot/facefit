import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, MousePointerClick, Users } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { Card, SectionTitle } from "../components/ui";

export function Dashboard() {
  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: () => apiRequest<any>("/api/dashboard/stats") });
  const cards = data?.cards || {};
  const conversion = data?.conversion || {};
  return (
    <div>
      <SectionTitle title="Dashboard" subtitle="Воронка, последние заявки и состояние AI-пайплайна" />
      {isLoading ? <p>Загружаю...</p> : null}
      <div className="grid gap-4 md:grid-cols-4">
        {[
          ["Пользователи", cards.users, Users],
          ["Новые заявки", cards.new_leads, MousePointerClick],
          ["Завершенные анализы", cards.completed_analyses, CheckCircle2],
          ["Ошибки AI", cards.ai_errors, AlertTriangle]
        ].map(([label, value, Icon]) => (
          <Card key={String(label)}>
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-clay">{String(label)}</p>
              <Icon className="text-rose" size={20} />
            </div>
            <p className="mt-4 text-3xl font-bold">{String(value ?? 0)}</p>
          </Card>
        ))}
      </div>
      <div className="mt-6 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <h2 className="mb-4 font-bold">Заявки по дням</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data?.requests_by_day || []}>
                <CartesianGrid stroke="#eadbd1" />
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#be7d86" strokeWidth={3} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 font-bold">Топ проблем</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.top_problems || []}>
                <XAxis dataKey="title" hide />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#7b967c" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <Card>
          <h2 className="mb-4 font-bold">Конверсия</h2>
          <div className="space-y-3 text-sm">
            <p>start → photo: <strong>{conversion.start_to_photo ?? 0}%</strong></p>
            <p>photo → analysis: <strong>{conversion.photo_to_analysis ?? 0}%</strong></p>
            <p>analysis → report opened: <strong>{conversion.analysis_to_report_opened ?? 0}%</strong></p>
            <p>report → CTA: <strong>{conversion.report_to_cta ?? 0}%</strong></p>
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 font-bold">Последние заявки</h2>
          <div className="space-y-3">
            {(data?.latest_leads || []).map((lead: any) => (
              <Link key={lead.id} to={`/admin/leads/${lead.id}`} className="flex items-center justify-between rounded-card border border-pearl p-3 hover:bg-milk">
                <div>
                  <p className="font-semibold">{lead.name || "Без имени"}</p>
                  <p className="text-xs text-clay">{(lead.selected_problems || []).join(", ")}</p>
                </div>
                <StatusBadge status={lead.status} />
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

