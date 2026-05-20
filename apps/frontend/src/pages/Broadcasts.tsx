import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { Button, Card, Input, SectionTitle, Select, Textarea } from "../components/ui";

export function Broadcasts() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["broadcasts"], queryFn: () => apiRequest<any>("/api/broadcasts") });
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [segment, setSegment] = useState("all");
  const create = useMutation({
    mutationFn: () => apiRequest("/api/broadcasts", { method: "POST", body: JSON.stringify({ title, text, message_type: "text", audience_filter: { segment } }) }),
    onSuccess: () => {
      setTitle("");
      setText("");
      qc.invalidateQueries({ queryKey: ["broadcasts"] });
    }
  });
  const send = useMutation({
    mutationFn: (id: number) => apiRequest(`/api/broadcasts/${id}/send`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["broadcasts"] })
  });
  return (
    <div>
      <SectionTitle title="Рассылки" subtitle="Сегменты, preview и история отправок" />
      <div className="grid gap-5 lg:grid-cols-[420px_1fr]">
        <Card>
          <h2 className="mb-4 font-bold">Новая рассылка</h2>
          <div className="space-y-3">
            <Input placeholder="Название" value={title} onChange={(e) => setTitle(e.target.value)} />
            <Select value={segment} onChange={(e) => setSegment(e.target.value)}>
              <option value="all">Все пользователи</option>
              <option value="no_photo">Не отправили фото</option>
              <option value="got_report">Получили отчет</option>
              <option value="report_opened">Открыли отчет</option>
              <option value="no_cta">Не нажали CTA</option>
            </Select>
            <Textarea placeholder="Текст сообщения" value={text} onChange={(e) => setText(e.target.value)} />
            <div className="rounded-card bg-milk p-4 text-sm">
              <p className="mb-2 font-semibold text-clay">Preview</p>
              <p>{text || "Текст рассылки появится здесь"}</p>
            </div>
            <Button onClick={() => create.mutate()} disabled={!title || !text}>Создать draft</Button>
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 font-bold">История</h2>
          <div className="space-y-3">
            {(data?.items || []).map((item: any) => (
              <div key={item.id} className="rounded-card border border-pearl p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-bold">{item.title}</p>
                    <p className="text-xs text-clay">{item.status} · получателей: {item.recipients?.length || 0}</p>
                  </div>
                  <Button variant="secondary" onClick={() => send.mutate(item.id)}><Send size={16} />Отправить</Button>
                </div>
                <p className="mt-3 text-sm">{item.text}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

