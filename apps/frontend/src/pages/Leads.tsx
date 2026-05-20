import { useQuery } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { apiBase, apiRequest } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { Button, Card, Input, SectionTitle, Select } from "../components/ui";

export function Leads() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const { data } = useQuery({
    queryKey: ["leads", search, status],
    queryFn: () => apiRequest<any>(`/api/leads?search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}`)
  });
  return (
    <div>
      <SectionTitle title="Лиды" subtitle="Пользователи, выбранные проблемы, статусы, заметки и отчет" />
      <Card className="mb-5">
        <div className="grid gap-3 md:grid-cols-[1fr_220px_auto]">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 text-clay" size={17} />
            <Input className="pl-10" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по имени или username" />
          </div>
          <Select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Все статусы</option>
            <option value="WAITING_FOR_PHOTO">Ждет фото</option>
            <option value="QUEUED">В очереди</option>
            <option value="COMPLETED">Готово</option>
            <option value="FAILED">Ошибка</option>
          </Select>
          <a href={`${apiBase}/api/leads/export`} target="_blank" rel="noreferrer">
            <Button variant="secondary" type="button">
              <Download size={16} />
              CSV
            </Button>
          </a>
        </div>
      </Card>
      <Card className="overflow-hidden p-0">
        <table className="w-full min-w-[920px] text-sm">
          <thead className="bg-pearl/60 text-left text-clay">
            <tr>
              <th className="p-4">Имя</th>
              <th className="p-4">Telegram</th>
              <th className="p-4">Статус</th>
              <th className="p-4">Проблемы</th>
              <th className="p-4">Отчет</th>
              <th className="p-4">CTA</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map((lead: any) => (
              <tr key={lead.id} className="border-t border-pearl">
                <td className="p-4 font-semibold"><Link to={`/admin/leads/${lead.id}`}>{lead.name || "Без имени"}</Link></td>
                <td className="p-4">@{lead.telegram_user?.username || "—"} · {lead.telegram_user?.telegram_id}</td>
                <td className="p-4"><StatusBadge status={lead.status} /></td>
                <td className="p-4">{(lead.selected_problems || []).join(", ")}</td>
                <td className="p-4">{lead.report_opened ? "Открывал" : "Нет"}</td>
                <td className="p-4">{lead.cta_clicked ? "Нажимал" : "Нет"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

