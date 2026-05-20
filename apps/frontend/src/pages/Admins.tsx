import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiRequest } from "../api/client";
import { Badge, Button, Card, Input, SectionTitle, Select } from "../components/ui";

export function Admins() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["admins"], queryFn: () => apiRequest<any>("/api/admins") });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("manager");
  const create = useMutation({
    mutationFn: () => apiRequest("/api/admins", { method: "POST", body: JSON.stringify({ email, password, role }) }),
    onSuccess: () => {
      setEmail("");
      setPassword("");
      qc.invalidateQueries({ queryKey: ["admins"] });
    }
  });
  const patch = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) =>
      apiRequest(`/api/admins/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admins"] })
  });
  return (
    <div>
      <SectionTitle title="Администраторы" subtitle="Роли owner, manager, viewer и отключение доступа" />
      <Card className="mb-5">
        <div className="grid gap-3 md:grid-cols-[1fr_180px_160px_auto]">
          <Input placeholder="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          <Input placeholder="пароль" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          <Select value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="owner">owner</option>
            <option value="manager">manager</option>
            <option value="viewer">viewer</option>
          </Select>
          <Button onClick={() => create.mutate()} disabled={!email || !password}>Создать</Button>
        </div>
      </Card>
      <Card className="overflow-hidden p-0">
        <table className="w-full min-w-[700px] text-sm">
          <thead className="bg-pearl/60 text-left text-clay">
            <tr><th className="p-4">Email</th><th className="p-4">Роль</th><th className="p-4">Статус</th><th className="p-4">Действия</th></tr>
          </thead>
          <tbody>
            {(data?.items || []).map((admin: any) => (
              <tr key={admin.id} className="border-t border-pearl">
                <td className="p-4 font-semibold">{admin.email}</td>
                <td className="p-4">{admin.role}</td>
                <td className="p-4"><Badge tone={admin.is_active ? "green" : "red"}>{admin.is_active ? "активен" : "отключен"}</Badge></td>
                <td className="p-4">
                  <Button
                    variant="secondary"
                    onClick={() => patch.mutate({ id: admin.id, payload: { is_active: !admin.is_active } })}
                  >
                    {admin.is_active ? "Отключить" : "Включить"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

