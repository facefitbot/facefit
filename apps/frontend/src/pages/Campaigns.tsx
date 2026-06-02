import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { Button, Card, Input, SectionTitle } from "../components/ui";

export function Campaigns() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["campaigns"], queryFn: () => apiRequest<any>("/api/campaigns") });
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const create = useMutation({
    mutationFn: () => apiRequest("/api/campaigns", { method: "POST", body: JSON.stringify({ slug, title }) }),
    onSuccess: () => {
      setSlug("");
      setTitle("");
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    }
  });
  return (
    <div>
      <SectionTitle title="UTM / Источники" subtitle="Deep-link ссылки вида /start campaign_x и конверсия по кампаниям" />
      <Card className="mb-5">
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Input placeholder="slug" value={slug} onChange={(e) => setSlug(e.target.value)} />
          <Input placeholder="Название кампании" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Button onClick={() => create.mutate()} disabled={!slug || !title}>Создать</Button>
        </div>
      </Card>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-pearl/60 text-left text-clay">
            <tr><th className="p-4">Кампания</th><th className="p-4">Ссылка</th><th className="p-4">Переходы</th><th className="p-4">Фото</th><th className="p-4">Отчеты</th><th className="p-4">CTA</th><th className="p-4">Конверсия</th></tr>
          </thead>
          <tbody>
            {(data?.items || []).map((item: any) => (
              <tr key={item.id} className="border-t border-pearl">
                <td className="p-4 font-semibold">{item.title}</td>
                <td className="p-4 text-rose">{item.url}</td>
                <td className="p-4">{item.clicks}</td>
                <td className="p-4">{item.photo_count}</td>
                <td className="p-4">{item.report_count}</td>
                <td className="p-4">{item.cta_clicks}</td>
                <td className="p-4">{item.conversion}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
