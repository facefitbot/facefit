import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, RefreshCcw, SearchCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { apiRequest, storageUrl } from "../api/client";
import { JsonViewer } from "../components/JsonViewer";
import { StatusBadge } from "../components/StatusBadge";
import { Badge, Button, Card, SectionTitle } from "../components/ui";

export function AnalysisDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["analysis", id], queryFn: () => apiRequest<any>(`/api/analysis/${id}`), enabled: Boolean(id) });
  const action = useMutation({
    mutationFn: (path: string) => apiRequest(`/api/analysis/${id}/${path}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["analysis", id] })
  });
  const approveVariant = useMutation({
    mutationFn: (variant_path: string) =>
      apiRequest(`/api/analysis/${id}/after-photo/approve-variant`, {
        method: "POST",
        body: JSON.stringify({ variant_path })
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["analysis", id] })
  });
  const variantPaths = data?.after_photo_variant_paths || [];
  if (!data) return <p>Загружаю...</p>;
  return (
    <div>
      <SectionTitle title={`Анализ #${data.id}`} subtitle={data.lead?.name || "Без имени"} />
      <div className="mb-5 flex flex-wrap gap-2">
        <StatusBadge status={data.status} />
        <Button variant="secondary" onClick={() => action.mutate("retry")}><RefreshCcw size={16} />Перегенерировать анализ</Button>
        <Button variant="secondary" onClick={() => action.mutate("regenerate-personal-insights")}>Перегенерировать personal insights</Button>
        <Button variant="secondary" onClick={() => action.mutate("regenerate-protocol-copy")}>Перегенерировать protocol copy</Button>
        <Button variant="secondary" onClick={() => action.mutate("regenerate-face-protocol")}>Перегенерировать face protocol PNG</Button>
        <Button variant="secondary" onClick={() => action.mutate("regenerate-report")}>Перегенерировать отчет</Button>
        <Button variant="secondary" onClick={() => action.mutate("regenerate-after-photo")}>Перегенерировать after-photo</Button>
        <Button variant="secondary" onClick={() => action.mutate("regenerate-after-photo/subtle")}>Subtle</Button>
        <Button variant="secondary" onClick={() => action.mutate("regenerate-after-photo/balanced")}>Balanced</Button>
        <Button variant="secondary" onClick={() => action.mutate("regenerate-after-photo/visible")}>Visible</Button>
        <Button variant="secondary" onClick={() => action.mutate("after-photo/needs-manual-review")}><SearchCheck size={16} />Manual review</Button>
        {data.report_token ? <Link to={`/report/${data.report_token}`} target="_blank"><Button type="button">Открыть отчет</Button></Link> : null}
      </div>
      {data.error_message ? <Card className="mb-5 border-red-200 bg-red-50 text-red-900">{data.error_message}</Card> : null}
      <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
        <div className="space-y-5">
          <Card>
            <h2 className="mb-3 font-bold">Заявка</h2>
            <div className="space-y-2 text-sm">
              <p><span className="font-semibold">Выбранные зоны:</span> {(data.selected_problems || []).join(", ") || "не указаны"}</p>
              <p><span className="font-semibold">Public report:</span> {data.report_token ? <Link className="text-brand underline" to={`/report/${data.report_token}`} target="_blank">{data.report_token}</Link> : "не готов"}</p>
              <p><span className="font-semibold">After-photo status:</span> {data.after_photo_status || "не запускался"}</p>
              <p><span className="font-semibold">Intensity:</span> {data.after_photo_used_intensity || "balanced"}</p>
              <p><span className="font-semibold">Retry count:</span> {data.after_photo_retry_count || 0}</p>
            </div>
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">Изображения</h2>
            <div className="grid gap-3">
              <div>
                <p className="mb-1 text-xs font-semibold text-clay">Final face protocol PNG {data.face_protocol_version || data.protocol_version || "не готов"}</p>
                {data.face_protocol_image_path ? (
                  <img src={storageUrl(data.face_protocol_image_path)} alt="Final face protocol" className="w-full rounded-card border border-pearl object-cover" />
                ) : data.protocol_slide_paths?.length ? (
                  <div className="grid gap-2">
                    {data.protocol_slide_paths.map((path: string, index: number) => (
                      <img key={path} src={storageUrl(path)} alt={`Protocol slide ${index + 1}`} className="w-full rounded-card border border-pearl object-cover" />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-clay">Еще не готово</p>
                )}
              </div>
              {[
                ["Исходное", data.original_photo_path],
                ["Legacy фото-протокол", data.legacy_protocol_image_path],
                ["Final after-photo", data.after_photo_final_path || data.after_photo_path]
              ].map(([label, path]) => (
                <div key={label}>
                  <p className="mb-1 text-xs font-semibold text-clay">{label}</p>
                  {path ? <img src={storageUrl(String(path))} className="w-full rounded-card border border-pearl object-cover" /> : <p className="text-sm text-clay">Еще не готово</p>}
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="font-bold">After-photo variants</h2>
              <Badge tone={data.after_photo_status === "APPROVED" ? "green" : data.after_photo_status === "NEEDS_MANUAL_REVIEW" ? "yellow" : "neutral"}>
                {data.after_photo_status || "PENDING"}
              </Badge>
            </div>
            {variantPaths.length ? (
              <div className="grid gap-3">
                {variantPaths.map((path: string, index: number) => (
                  <div key={path} className="rounded-card border border-pearl p-3">
                    <p className="mb-2 text-xs font-semibold text-clay">Variant {index + 1}</p>
                    <img src={storageUrl(path)} alt={`After-photo variant ${index + 1}`} className="w-full rounded-card border border-pearl object-cover" />
                    <Button
                      className="mt-3 w-full"
                      variant="secondary"
                      disabled={approveVariant.isPending}
                      onClick={() => approveVariant.mutate(path)}
                    >
                      <CheckCircle2 size={16} />Approve variant manually
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-clay">Варианты еще не созданы.</p>
            )}
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">AI логи</h2>
            <div className="space-y-3">
              {(data.ai_logs || []).map((log: any) => (
                <div key={log.id} className="rounded-card border border-pearl p-3 text-sm">
                  <p className="font-semibold">{log.stage} · {log.status}</p>
                  <p className="text-clay">{log.message}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
        <div className="space-y-5">
          <Card>
            <h2 className="mb-3 font-bold">JSON-анализ</h2>
            <JsonViewer value={data.analysis_json} />
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">Personal insight JSON</h2>
            <JsonViewer value={data.personal_insight_json} />
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">Protocol copy JSON</h2>
            <JsonViewer value={data.protocol_copy_json} />
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">Report JSON</h2>
            <JsonViewer value={data.report_json} />
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">After-photo plan</h2>
            <JsonViewer value={data.after_photo_plan} />
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">After-photo variants</h2>
            <JsonViewer value={data.after_photo_variants} />
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">After-photo variant paths</h2>
            <JsonViewer value={data.after_photo_variant_paths} />
          </Card>
          <Card>
            <h2 className="mb-3 font-bold">After-photo QC results</h2>
            <JsonViewer value={data.after_photo_quality_results} />
          </Card>
        </div>
      </div>
    </div>
  );
}
