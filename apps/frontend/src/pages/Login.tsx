import { useMutation } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiRequest } from "../api/client";
import { Button, Card, Input } from "../components/ui";
import { useAuthStore } from "../shared/authStore";

export function Login() {
  const navigate = useNavigate();
  const setToken = useAuthStore((state) => state.setToken);
  const [email, setEmail] = useState("admin@bellavladi.local");
  const [password, setPassword] = useState("admin12345");
  const mutation = useMutation({
    mutationFn: () => apiRequest<{ access_token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
    onSuccess: (data) => {
      setToken(data.access_token);
      navigate("/admin/dashboard");
    }
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };
  return (
    <div className="grid min-h-screen place-items-center bg-milk p-5">
      <Card className="w-full max-w-md">
        <div className="mb-7 flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-card bg-rose text-white">
            <Sparkles />
          </div>
          <div>
            <h1 className="text-xl font-bold">Bella Vladi Admin</h1>
            <p className="text-sm text-clay">Вход в панель face-протоколов</p>
          </div>
        </div>
        <form className="space-y-4" onSubmit={submit}>
          <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" type="email" />
          <Input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Пароль" type="password" />
          {mutation.error ? <p className="text-sm text-red-700">{mutation.error.message}</p> : null}
          <Button className="w-full" disabled={mutation.isPending}>
            Войти
          </Button>
        </form>
      </Card>
    </div>
  );
}

