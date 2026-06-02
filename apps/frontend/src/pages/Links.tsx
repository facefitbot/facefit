import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, ExternalLink, Link as LinkIcon, MousePointerClick, QrCode, Search, ToggleLeft, ToggleRight, Trash2, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { apiRequest } from "../api/client";
import { Badge, Button, Card, Input, SectionTitle, Select, Textarea } from "../components/ui";
import { formatDate, tagColorStyle } from "./crmShared";

type Options = {
  audiences: { id: number; name: string; color?: string }[];
  managers: { id: number; name?: string | null; email: string }[];
  tags: { id: number; name: string; color?: string }[];
};
type SourceLink = {
  id: number;
  name: string;
  slug: string;
  full_url: string;
  source?: string | null;
  source_label?: string;
  campaign?: string | null;
  description?: string | null;
  audience?: { id: number; name: string; color?: string } | null;
  tags: string[];
  funnel_id?: number | null;
  assigned_manager?: { id: number; email: string } | null;
  is_active: boolean;
  created_at?: string;
  metrics: {
    clicks: number;
    unique_users: number;
    new_users: number;
    applications: number;
    purchases: number;
    click_to_application: number;
    application_to_purchase: number;
    last_touch_at?: string | null;
  };
};
type LinksResponse = {
  items: SourceLink[];
  sources: { value: string; label: string }[];
};

const initialForm = {
  name: "",
  slug: "",
  source: "instagram",
  campaign: "",
  description: "",
  audience_id: "",
  tags: "",
  funnel_id: "",
  assigned_manager_id: "",
  is_active: true
};

export function Links() {
  const qc = useQueryClient();
  const [form, setForm] = useState(initialForm);
  const [qrUrl, setQrUrl] = useState("");
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("active");
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const { data } = useQuery<LinksResponse>({ queryKey: ["source-links"], queryFn: () => apiRequest("/api/admin/links") });
  const { data: options } = useQuery<Options>({ queryKey: ["crm-options"], queryFn: () => apiRequest("/api/admin/crm/options") });
  const links = data?.items || [];
  const sourceOptions = data?.sources || [];
  const filteredLinks = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return links.filter((link) => {
      const matchesSearch = !needle || [link.name, link.slug, link.full_url, link.source, link.campaign, link.description, ...link.tags]
        .filter(Boolean)
        .some((item) => String(item).toLowerCase().includes(needle));
      const matchesSource = !sourceFilter || link.source === sourceFilter;
      const matchesStatus = statusFilter === "all" || (statusFilter === "active" ? link.is_active : !link.is_active);
      return matchesSearch && matchesSource && matchesStatus;
    });
  }, [links, search, sourceFilter, statusFilter]);
  const totals = useMemo(() => {
    return links.reduce(
      (acc, link) => {
        acc.clicks += link.metrics.clicks;
        acc.newUsers += link.metrics.new_users;
        acc.applications += link.metrics.applications;
        acc.purchases += link.metrics.purchases;
        return acc;
      },
      { clicks: 0, newUsers: 0, applications: 0, purchases: 0 }
    );
  }, [links]);
  const create = useMutation({
    mutationFn: () =>
      apiRequest("/api/admin/links", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          slug: form.slug,
          source: form.source,
          campaign: form.campaign || null,
          description: form.description || null,
          audience_id: form.audience_id ? Number(form.audience_id) : null,
          tags: form.tags.split(",").map((item) => item.trim()).filter(Boolean),
          funnel_id: form.funnel_id ? Number(form.funnel_id) : null,
          assigned_manager_id: form.assigned_manager_id ? Number(form.assigned_manager_id) : null,
          is_active: form.is_active
        })
      }),
    onSuccess: () => {
      setForm(initialForm);
      qc.invalidateQueries({ queryKey: ["source-links"] });
      qc.invalidateQueries({ queryKey: ["crm-options"] });
    }
  });
  const patch = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) =>
      apiRequest(`/api/admin/links/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["source-links"] });
      qc.invalidateQueries({ queryKey: ["crm-options"] });
    }
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiRequest(`/api/admin/links/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["source-links"] })
  });
  const setField = (key: keyof typeof initialForm, value: string | boolean) => setForm((current) => ({ ...current, [key]: value }));
  const copy = async (id: number, url: string) => {
    await navigator.clipboard.writeText(url);
    setCopiedId(id);
    window.setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1600);
  };
  return (
    <div>
      <SectionTitle title="Базы и ссылки" subtitle="Deep links для Telegram-бота: источник, кампания, база, теги и метрики" />
      <div className="mb-5 grid gap-3 md:grid-cols-4">
        <Card className="p-4"><p className="text-xs font-semibold text-clay">Активные ссылки</p><p className="mt-2 text-2xl font-bold">{links.filter((item) => item.is_active).length}</p></Card>
        <Card className="p-4"><p className="text-xs font-semibold text-clay">Переходы</p><p className="mt-2 text-2xl font-bold">{totals.clicks}</p></Card>
        <Card className="p-4"><p className="text-xs font-semibold text-clay">Новые пользователи</p><p className="mt-2 text-2xl font-bold">{totals.newUsers}</p></Card>
        <Card className="p-4"><p className="text-xs font-semibold text-clay">Заявки / покупки</p><p className="mt-2 text-2xl font-bold">{totals.applications} / {totals.purchases}</p></Card>
      </div>
      <div className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Card className="self-start">
          <div className="mb-4 flex items-center gap-2 font-bold">
            <LinkIcon size={18} />
            Новая ссылка
          </div>
          <div className="space-y-3">
            <Input placeholder="Название" value={form.name} onChange={(event) => setField("name", event.target.value)} />
            <Input placeholder="slug / код" value={form.slug} onChange={(event) => setField("slug", event.target.value)} />
            <div className="grid gap-3 sm:grid-cols-2">
              <Select value={form.source} onChange={(event) => setField("source", event.target.value)}>
                {sourceOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </Select>
              <Input placeholder="Кампания" value={form.campaign} onChange={(event) => setField("campaign", event.target.value)} />
            </div>
            <Select value={form.audience_id} onChange={(event) => setField("audience_id", event.target.value)}>
              <option value="">База / аудитория</option>
              {(options?.audiences || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </Select>
            <Input placeholder="Авто-теги через запятую" value={form.tags} onChange={(event) => setField("tags", event.target.value)} />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input placeholder="ID сценария" value={form.funnel_id} onChange={(event) => setField("funnel_id", event.target.value)} />
              <Select value={form.assigned_manager_id} onChange={(event) => setField("assigned_manager_id", event.target.value)}>
                <option value="">Ответственный</option>
                {(options?.managers || []).map((item) => <option key={item.id} value={item.id}>{item.name || item.email}</option>)}
              </Select>
            </div>
            <Textarea className="min-h-20" placeholder="Описание" value={form.description} onChange={(event) => setField("description", event.target.value)} />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex h-10 items-center gap-2 rounded-card border border-pearl bg-white px-3 text-sm font-semibold">
                <input type="checkbox" checked={form.is_active} onChange={(event) => setField("is_active", event.target.checked)} />
                Активна
              </label>
              <Button type="button" onClick={() => create.mutate()} disabled={!form.name || !form.slug}>
                Создать
              </Button>
            </div>
          </div>
        </Card>
        <div className="min-w-0 space-y-4">
          <Card>
            <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_180px_150px]">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 text-clay" size={17} />
                <Input className="pl-10" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по названию, slug, кампании, тегам" />
              </div>
              <Select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}>
                <option value="">Все источники</option>
                {sourceOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </Select>
              <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="active">Активные</option>
                <option value="inactive">Отключенные</option>
                <option value="all">Все</option>
              </Select>
            </div>
          </Card>
          <div className="grid gap-3 lg:grid-cols-2">
            {filteredLinks.map((link) => (
              <Card key={link.id} className={`p-4 ${link.is_active ? "" : "opacity-70"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="truncate font-bold">{link.name}</h2>
                      <Badge tone={link.is_active ? "green" : "red"}>{link.is_active ? "активна" : "выкл"}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-clay">{link.source_label || link.source || "Источник"} · {link.campaign || "без кампании"} · {formatDate(link.created_at)}</p>
                  </div>
                  <button type="button" onClick={() => patch.mutate({ id: link.id, payload: { is_active: !link.is_active } })} className="inline-flex shrink-0 items-center gap-1 text-sm font-semibold">
                    {link.is_active ? <ToggleRight className="text-sage" size={26} /> : <ToggleLeft className="text-clay" size={26} />}
                  </button>
                </div>
                <div className="mt-3 rounded-card border border-pearl bg-milk px-3 py-2">
                  <p className="break-all text-sm font-semibold text-rose">{link.full_url}</p>
                  <p className="mt-1 text-xs text-clay">slug: {link.slug} · последний переход: {formatDate(link.metrics.last_touch_at)}</p>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  <div className="rounded-card bg-milk p-2"><MousePointerClick size={15} className="mb-1 text-rose" /><b>{link.metrics.clicks}</b><p className="text-xs text-clay">переходы</p></div>
                  <div className="rounded-card bg-milk p-2"><Users size={15} className="mb-1 text-rose" /><b>{link.metrics.new_users}</b><p className="text-xs text-clay">новые</p></div>
                  <div className="rounded-card bg-milk p-2"><b>{link.metrics.applications}</b><p className="text-xs text-clay">заявки</p></div>
                  <div className="rounded-card bg-milk p-2"><b>{link.metrics.click_to_application}%</b><p className="text-xs text-clay">конверсия</p></div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1">
                  {link.audience ? <span style={{ color: link.audience.color }} className="rounded-full bg-pearl px-2 py-1 text-xs font-semibold">{link.audience.name}</span> : null}
                  {link.tags.length ? link.tags.map((tag) => <span key={tag} className="rounded-full px-2 py-1 text-xs font-semibold" style={tagColorStyle()}>{tag}</span>) : null}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button className="h-9 px-3" variant="secondary" type="button" onClick={() => void copy(link.id, link.full_url)}>
                    <Copy size={15} />
                    {copiedId === link.id ? "Скопировано" : "Копировать"}
                  </Button>
                  <a className="inline-flex h-9 items-center justify-center gap-2 rounded-card bg-pearl px-3 text-sm font-semibold text-ink hover:bg-[#ead9cf]" href={link.full_url} target="_blank" rel="noreferrer"><ExternalLink size={15} />Открыть</a>
                  <Button className="h-9 px-3" variant="ghost" type="button" onClick={() => setQrUrl(link.full_url)}><QrCode size={15} />QR</Button>
                  <Button className="h-9 px-3" variant="danger" type="button" onClick={() => remove.mutate(link.id)}><Trash2 size={15} /></Button>
                </div>
              </Card>
            ))}
            {!filteredLinks.length ? (
              <Card className="p-8 text-center text-clay">Ссылок не найдено</Card>
            ) : null}
          </div>
        </div>
      </div>
      {qrUrl ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/35 p-4" onClick={() => setQrUrl("")}>
          <div className="rounded-card bg-white p-5 shadow-soft" onClick={(event) => event.stopPropagation()}>
            <img alt="QR code" className="h-64 w-64" src={`https://api.qrserver.com/v1/create-qr-code/?size=256x256&data=${encodeURIComponent(qrUrl)}`} />
            <p className="mt-3 max-w-64 break-all text-center text-xs text-clay">{qrUrl}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
