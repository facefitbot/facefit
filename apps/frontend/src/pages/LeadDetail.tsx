import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { Button, Card, Input, SectionTitle, Select, Textarea } from "../components/ui";

export function LeadDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["lead", id], queryFn: () => apiRequest<any>(`/api/leads/${id}`), enabled: Boolean(id) });
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState("");
  const [tags, setTags] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/leads/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          manager_comment: comment || data?.manager_comment,
          status: status || data?.status,
          tags: tags ? tags.split(",").map((item) => item.trim()).filter(Boolean) : data?.tags
        })
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lead", id] })
  });
  if (!data) return <p>Загружаю...</p>;
  return (
    <div>
      <SectionTitle title={data.name || "Лид"} subtitle={`Telegram ID: ${data.telegram_user?.telegram_id || "—"}`} />
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <Card>
          <div className="mb-4 flex items-center gap-3">
            <StatusBadge status={data.status} />
            <span className="text-sm text-clay">@{data.telegram_user?.username || "—"}</span>
          </div>
          <p className="text-sm"><strong>Проблемы:</strong> {(data.selected_problems || []).join(", ") || "—"}</p>
          <p className="mt-2 text-sm"><strong>Источник:</strong> {data.source || "—"}</p>
          <p className="mt-2 text-sm"><strong>Открывал отчет:</strong> {data.report_opened ? "да" : "нет"}</p>
          <p className="mt-2 text-sm"><strong>Нажимал CTA:</strong> {data.cta_clicked ? "да" : "нет"}</p>
          <h2 className="mt-6 font-bold">Анализы</h2>
          <div className="mt-3 space-y-3">
            {(data.analyses || []).map((analysis: any) => (
              <Link key={analysis.id} to={`/admin/analysis/${analysis.id}`} className="flex items-center justify-between rounded-card border border-pearl p-3 hover:bg-milk">
                <span>Анализ #{analysis.id}</span>
                <StatusBadge status={analysis.status} />
              </Link>
            ))}
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 font-bold">Менеджер</h2>
          <label className="text-xs font-semibold text-clay">Статус</label>
          <Select className="mt-1" value={status || data.status} onChange={(event) => setStatus(event.target.value)}>
            {["WAITING_FOR_PHOTO", "QUEUED", "COMPLETED", "FAILED", "NEEDS_REVIEW"].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </Select>
          <label className="mt-4 block text-xs font-semibold text-clay">Теги через запятую</label>
          <Input className="mt-1" defaultValue={(data.tags || []).join(", ")} onChange={(event) => setTags(event.target.value)} />
          <label className="mt-4 block text-xs font-semibold text-clay">Комментарий</label>
          <Textarea className="mt-1" defaultValue={data.manager_comment || ""} onChange={(event) => setComment(event.target.value)} />
          <Button className="mt-4 w-full" onClick={() => mutation.mutate()}>Сохранить</Button>
        </Card>
      </div>
    </div>
  );
}

