import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Download, Megaphone, Plus, Save, Search, Trash2, Upload, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiBase, apiRequest } from "../api/client";
import { Badge, Button, Card, Input, SectionTitle, Select, Textarea } from "../components/ui";
import { CRM_STATUSES, CrmStatusBadge, formatDate } from "./crmShared";

type Base = {
  id: number;
  name: string;
  description?: string | null;
  type: "static" | "dynamic";
  filters_json: Record<string, unknown>;
  members_count: number;
  active_users: number;
  blocked_or_unsubscribed: number;
  created_at?: string;
  last_broadcast?: { id: number; title: string; status: string } | null;
};

async function exportBase(id: number) {
  const token = localStorage.getItem("bella_admin_token");
  const response = await fetch(`${apiBase}/api/admin/bases/${id}/export`, {
    headers: { Authorization: token ? `Bearer ${token}` : "", "ngrok-skip-browser-warning": "true" }
  });
  if (!response.ok) throw new Error("Не удалось экспортировать базу");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `base_${id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function Audiences() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<"static" | "dynamic">("static");
  const [filtersJson, setFiltersJson] = useState("{}");
  const [dynamicStatus, setDynamicStatus] = useState("");
  const [dynamicProblem, setDynamicProblem] = useState("");
  const [dynamicReportOpened, setDynamicReportOpened] = useState("");
  const [dynamicCtaClicked, setDynamicCtaClicked] = useState("");
  const [selectedBaseId, setSelectedBaseId] = useState<number | null>(null);
  const [memberIds, setMemberIds] = useState("");
  const [search, setSearch] = useState("");
  const [baseSearch, setBaseSearch] = useState("");
  const [baseTypeFilter, setBaseTypeFilter] = useState("");
  const [detailPage, setDetailPage] = useState(1);
  const { data } = useQuery<{ items: Base[] }>({ queryKey: ["bases"], queryFn: () => apiRequest("/api/admin/bases") });
  const selectedBase = selectedBaseId || data?.items?.[0]?.id || null;
  const { data: detail } = useQuery<any>({
    queryKey: ["base-detail", selectedBase, search, detailPage],
    queryFn: () => apiRequest(`/api/admin/bases/${selectedBase}?search=${encodeURIComponent(search)}&page=${detailPage}&page_size=25`),
    enabled: Boolean(selectedBase)
  });
  const create = useMutation({
    mutationFn: () => {
      let parsed: Record<string, unknown> = {};
      if (type === "dynamic") {
        parsed = JSON.parse(filtersJson || "{}");
        if (dynamicStatus) parsed.status = dynamicStatus;
        if (dynamicProblem.trim()) parsed.problem = dynamicProblem.trim();
        if (dynamicReportOpened) parsed.report_opened = dynamicReportOpened === "true";
        if (dynamicCtaClicked) parsed.cta_clicked = dynamicCtaClicked === "true";
      }
      return apiRequest("/api/admin/bases", { method: "POST", body: JSON.stringify({ name, description, type, filters_json: parsed }) });
    },
    onSuccess: () => {
      setName("");
      setDescription("");
      setFiltersJson("{}");
      setDynamicStatus("");
      setDynamicProblem("");
      setDynamicReportOpened("");
      setDynamicCtaClicked("");
      qc.invalidateQueries({ queryKey: ["bases"] });
      qc.invalidateQueries({ queryKey: ["crm-options"] });
    }
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiRequest(`/api/admin/bases/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setSelectedBaseId(null);
      qc.invalidateQueries({ queryKey: ["bases"] });
    }
  });
  const addMembers = useMutation({
    mutationFn: () => apiRequest(`/api/admin/bases/${selectedBase}/members`, { method: "POST", body: JSON.stringify({ lead_ids: memberIds.split(/[,\s]+/).map((item) => Number(item)).filter(Boolean) }) }),
    onSuccess: () => {
      setMemberIds("");
      qc.invalidateQueries({ queryKey: ["base-detail"] });
      qc.invalidateQueries({ queryKey: ["bases"] });
    }
  });
  const removeMember = useMutation({
    mutationFn: (leadId: number) => apiRequest(`/api/admin/bases/${selectedBase}/members/${leadId}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["base-detail"] });
      qc.invalidateQueries({ queryKey: ["bases"] });
    }
  });
  const importCsv = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return apiRequest(`/api/admin/bases/${selectedBase}/import`, { method: "POST", body });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["base-detail"] });
      qc.invalidateQueries({ queryKey: ["bases"] });
    }
  });
  const bases = data?.items || [];
  const filteredBases = useMemo(() => {
    const needle = baseSearch.trim().toLowerCase();
    return bases.filter((item) => {
      const matchesText = !needle || [item.name, item.description, item.type].filter(Boolean).some((value) => String(value).toLowerCase().includes(needle));
      const matchesType = !baseTypeFilter || item.type === baseTypeFilter;
      return matchesText && matchesType;
    });
  }, [bases, baseSearch, baseTypeFilter]);
  const totalMembers = bases.reduce((sum, item) => sum + item.members_count, 0);
  return (
    <div>
      <SectionTitle title="Базы" subtitle="Static базы и dynamic segments для CRM и рассылок" />
      <div className="mb-5 grid gap-3 md:grid-cols-4">
        <Card className="p-4"><p className="text-xs font-semibold text-clay">Всего баз</p><p className="mt-2 text-2xl font-bold">{bases.length}</p></Card>
        <Card className="p-4"><p className="text-xs font-semibold text-clay">Людей во всех базах</p><p className="mt-2 text-2xl font-bold">{totalMembers}</p></Card>
        <Card className="p-4"><p className="text-xs font-semibold text-clay">Активных</p><p className="mt-2 text-2xl font-bold">{bases.reduce((sum, item) => sum + item.active_users, 0)}</p></Card>
        <Card className="p-4"><p className="text-xs font-semibold text-clay">Исключены</p><p className="mt-2 text-2xl font-bold">{bases.reduce((sum, item) => sum + item.blocked_or_unsubscribed, 0)}</p></Card>
      </div>
      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        <div className="space-y-5">
          <Card>
            <div className="mb-4 flex items-center gap-2 font-bold"><Database size={18} />Новая база</div>
            <div className="space-y-3">
              <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Название базы" />
              <Select value={type} onChange={(event) => setType(event.target.value as "static" | "dynamic")}>
                <option value="static">Статическая база</option>
                <option value="dynamic">Динамический сегмент</option>
              </Select>
              <Textarea className="min-h-20" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Описание" />
              {type === "dynamic" ? (
                <div className="space-y-3 rounded-card border border-pearl bg-milk p-3">
                  <Select value={dynamicStatus} onChange={(event) => setDynamicStatus(event.target.value)}>
                    <option value="">Любой статус</option>
                    {CRM_STATUSES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </Select>
                  <Input value={dynamicProblem} onChange={(event) => setDynamicProblem(event.target.value)} placeholder="Проблема" />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Select value={dynamicReportOpened} onChange={(event) => setDynamicReportOpened(event.target.value)}>
                      <option value="">Отчет: все</option>
                      <option value="true">Открывали</option>
                      <option value="false">Не открывали</option>
                    </Select>
                    <Select value={dynamicCtaClicked} onChange={(event) => setDynamicCtaClicked(event.target.value)}>
                      <option value="">CTA: все</option>
                      <option value="true">Нажимали</option>
                      <option value="false">Не нажимали</option>
                    </Select>
                  </div>
                  <Textarea className="min-h-20 font-mono text-xs" value={filtersJson} onChange={(event) => setFiltersJson(event.target.value)} placeholder='{"source":"instagram"}' />
                </div>
              ) : null}
              <Button type="button" onClick={() => create.mutate()} disabled={!name.trim()}><Plus size={16} />Создать</Button>
            </div>
          </Card>
          <Card className="p-4">
            <div className="grid gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 text-clay" size={17} />
                <Input className="pl-10" value={baseSearch} onChange={(event) => setBaseSearch(event.target.value)} placeholder="Поиск базы" />
              </div>
              <Select value={baseTypeFilter} onChange={(event) => setBaseTypeFilter(event.target.value)}>
                <option value="">Все типы</option>
                <option value="static">Static</option>
                <option value="dynamic">Dynamic</option>
              </Select>
            </div>
          </Card>
          <div className="space-y-3">
            {filteredBases.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setSelectedBaseId(item.id);
                  setDetailPage(1);
                }}
                className={`w-full rounded-card border p-4 text-left transition ${selectedBase === item.id ? "border-rose bg-white" : "border-pearl bg-white/80 hover:bg-white"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-bold">{item.name}</p>
                    <p className="mt-1 text-xs text-clay">{item.type} · {formatDate(item.created_at)}</p>
                  </div>
                  <Badge tone={item.type === "dynamic" ? "yellow" : "neutral"}>{item.members_count}</Badge>
                </div>
                <p className="mt-2 text-sm text-clay">{item.description || "Без описания"}</p>
              </button>
            ))}
            {!filteredBases.length ? <p className="rounded-card border border-dashed border-pearl p-4 text-sm text-clay">Баз не найдено</p> : null}
          </div>
        </div>
        <Card>
          {!detail ? <p className="text-sm text-clay">Выберите базу</p> : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold">{detail.name}</h2>
                  <p className="mt-1 text-sm text-clay">{detail.type} · {detail.members_count} участников · активных {detail.active_users}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" type="button" onClick={() => void exportBase(detail.id)}><Download size={16} />CSV</Button>
                  <Link to={`/admin/broadcasts?base_id=${detail.id}`} className="inline-flex h-10 items-center gap-2 rounded-card bg-pearl px-3 text-sm font-semibold"><Megaphone size={16} />Рассылка</Link>
                  <Button variant="danger" type="button" onClick={() => remove.mutate(detail.id)}><Trash2 size={16} /></Button>
                </div>
              </div>
              {detail.type === "static" ? (
                <div className="mt-5 grid gap-2 lg:grid-cols-[1fr_auto_auto]">
                  <Input value={memberIds} onChange={(event) => setMemberIds(event.target.value)} placeholder="Lead IDs через запятую" />
                  <Button type="button" disabled={!memberIds.trim()} onClick={() => addMembers.mutate()}><Save size={16} />Добавить</Button>
                  <label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-card bg-pearl px-3 text-sm font-semibold">
                    <Upload size={16} />
                    CSV
                    <input
                      className="hidden"
                      type="file"
                      accept=".csv,text/csv"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) importCsv.mutate(file);
                        event.currentTarget.value = "";
                      }}
                    />
                  </label>
                </div>
              ) : (
                <pre className="mt-5 overflow-auto rounded-card bg-milk p-3 text-xs">{JSON.stringify(detail.filters_json || {}, null, 2)}</pre>
              )}
              <div className="mt-5">
                <Input value={search} onChange={(event) => {
                  setSearch(event.target.value);
                  setDetailPage(1);
                }} placeholder="Поиск внутри базы" />
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[760px] text-sm">
                  <thead className="bg-pearl/60 text-left text-clay">
                    <tr>
                      <th className="p-3">Пользователь</th>
                      <th className="p-3">Статус</th>
                      <th className="p-3">Проблемы</th>
                      <th className="p-3">Сигналы</th>
                      <th className="p-3">Менеджер</th>
                      <th className="p-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.members || []).map((member: any) => (
                      <tr key={member.lead_id} className="border-t border-pearl">
                        <td className="p-3">
                          <p className="font-semibold">{member.name || member.username || "Без имени"}</p>
                          <p className="text-xs text-clay">@{member.username || "—"} · {member.telegram_id}</p>
                        </td>
                        <td className="p-3"><CrmStatusBadge status={member.crm_status} /></td>
                        <td className="p-3">{(member.selected_problems || []).join(", ") || "—"}</td>
                        <td className="p-3">{member.report_opened ? "report" : "—"} {member.cta_clicked ? "· CTA" : ""}</td>
                        <td className="p-3">{member.manager?.name || member.manager?.email || "—"}</td>
                        <td className="p-3">
                          <div className="flex gap-2">
                            <Link to={`/admin/crm?lead=${member.lead_id}`} className="inline-flex h-9 items-center gap-2 rounded-card bg-pearl px-3 font-semibold"><Users size={15} />CRM</Link>
                            {detail.type === "static" ? <Button className="h-9 px-3" variant="ghost" type="button" onClick={() => removeMember.mutate(member.lead_id)}><Trash2 size={15} /></Button> : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {detail.members_total > detail.page_size ? (
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-clay">
                  <span>{detail.members_total} участников · страница {detail.page}</span>
                  <div className="flex gap-2">
                    <Button type="button" variant="secondary" disabled={detailPage <= 1} onClick={() => setDetailPage((page) => Math.max(1, page - 1))}>Назад</Button>
                    <Button type="button" variant="secondary" disabled={detailPage * detail.page_size >= detail.members_total} onClick={() => setDetailPage((page) => page + 1)}>Далее</Button>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
