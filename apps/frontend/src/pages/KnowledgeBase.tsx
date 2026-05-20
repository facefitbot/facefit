import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { ChangeEvent, useState } from "react";

import { apiRequest } from "../api/client";
import { Button, Card, SectionTitle } from "../components/ui";

export function KnowledgeBase() {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data } = useQuery({ queryKey: ["knowledge"], queryFn: () => apiRequest<any>("/api/knowledge") });
  const detail = useQuery({ queryKey: ["knowledge", selectedId], queryFn: () => apiRequest<any>(`/api/knowledge/${selectedId}`), enabled: Boolean(selectedId) });
  const upload = useMutation({
    mutationFn: async () => {
      if (!file) return null;
      const form = new FormData();
      form.append("file", file);
      return apiRequest("/api/knowledge/upload", { method: "POST", body: form });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge"] })
  });
  const onFile = (event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] || null);
  return (
    <div>
      <SectionTitle title="База знаний" subtitle="PDF, DOCX, TXT и Markdown документы для RAG в анализе и отчете" />
      <Card className="mb-5">
        <div className="flex flex-wrap items-center gap-3">
          <input type="file" accept=".pdf,.docx,.txt,.md,.markdown" onChange={onFile} />
          <Button onClick={() => upload.mutate()} disabled={!file || upload.isPending}><Upload size={16} />Загрузить</Button>
        </div>
      </Card>
      <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
        <Card>
          <h2 className="mb-4 font-bold">Документы</h2>
          <div className="space-y-2">
            {(data?.items || []).map((doc: any) => (
              <button key={doc.id} onClick={() => setSelectedId(doc.id)} className="w-full rounded-card border border-pearl p-3 text-left hover:bg-milk">
                <p className="font-semibold">{doc.title}</p>
                <p className="text-xs text-clay">{doc.chunk_count} chunks · {doc.is_active ? "включен" : "выключен"}</p>
              </button>
            ))}
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 font-bold">Chunks</h2>
          <div className="space-y-3">
            {(detail.data?.chunks || []).map((chunk: any) => (
              <div key={chunk.id} className="rounded-card border border-pearl bg-milk p-3 text-sm leading-relaxed">
                <p className="mb-2 font-semibold text-clay">Chunk #{chunk.chunk_index}</p>
                {chunk.content}
              </div>
            ))}
            {!selectedId ? <p className="text-sm text-clay">Выберите документ, чтобы посмотреть chunks.</p> : null}
          </div>
        </Card>
      </div>
    </div>
  );
}

