export type ChatSettings = {
  chat_id: number;
  mode: "strict" | "balanced" | "relaxed";
  ai_enabled: boolean;
  ai_threshold: number;
  action_policy: string;
  rate_limit_policy: string;
  language: string;
  level3_mute_seconds: number;
};

type ApiEnvelope<T> = {
  ok: boolean;
  data: T;
  error: string | null;
};

export type RuntimeState = {
  state: "setup" | "active";
  config_complete: boolean;
  config_version: number;
  run_mode: "polling" | "webhook";
};

export type SetupState = {
  state: "setup" | "active";
  config_complete: boolean;
  runtime_config: Record<string, unknown>;
};

export type AuditRecord = {
  id: number;
  chat_id: number;
  message_id: number;
  user_id: number;
  rule_hit: string;
  ai_used: number;
  ai_model: string | null;
  final_level: number;
  confidence: number;
  created_at: string;
};

export type EnforcementRecord = {
  id: number;
  chat_id: number;
  user_id: number;
  message_id: number;
  action: string;
  duration_seconds: number | null;
  reason: string;
  operator: string;
  created_at: string;
};

export type AppealRecord = {
  id: number;
  chat_id: number;
  user_id: number;
  message: string;
  created_at: string;
};

export type ListItem = {
  id: number;
  type: string;
  value: string;
  created_at: string;
};

export class ApiClient {
  constructor(private readonly baseUrl: string) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`, init);
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${text}`);
    }
    const data = (await resp.json()) as ApiEnvelope<T>;
    if (!data.ok) {
      throw new Error(data.error ?? "Unknown API error");
    }
    return data.data;
  }

  private adminHeaders(adminToken: string): HeadersInit {
    return {
      "Content-Type": "application/json",
      "X-Admin-Token": adminToken,
    };
  }

  private setupHeaders(setupToken: string): HeadersInit {
    return {
      "Content-Type": "application/json",
      "X-Setup-Token": setupToken,
    };
  }

  getRuntimeState() {
    return this.request<RuntimeState>("/api/v1/runtime/state");
  }

  getSetupState() {
    return this.request<SetupState>("/api/v1/setup/state");
  }

  setupAuth(code: string) {
    return this.request<{ setup_token: string; expires_in_minutes: number }>("/api/v1/setup/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
  }

  setupReissueCode() {
    return this.request<{ code: string; expires_in_minutes: number }>("/api/v1/setup/reissue-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  }

  setupConfig(setupToken: string, payload: Record<string, unknown>) {
    return this.request<{ saved: boolean; config: Record<string, unknown> }>("/api/v1/setup/config", {
      method: "POST",
      headers: this.setupHeaders(setupToken),
      body: JSON.stringify(payload),
    });
  }

  setupActivate(setupToken: string) {
    return this.request<RuntimeState>("/api/v1/setup/activate", {
      method: "POST",
      headers: this.setupHeaders(setupToken),
    });
  }

  getStatus(adminToken: string) {
    return this.request<Record<string, unknown>>("/api/v1/status", {
      headers: this.adminHeaders(adminToken),
    });
  }

  getSettings(chatId: string, adminToken: string) {
    return this.request<ChatSettings>(`/api/v1/chats/${chatId}/settings`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  updateSettings(chatId: string, adminToken: string, payload: Partial<ChatSettings>) {
    return this.request<ChatSettings>(`/api/v1/chats/${chatId}/settings`, {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  listWhitelist(chatId: string, adminToken: string) {
    return this.request<ListItem[]>(`/api/v1/chats/${chatId}/whitelist`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  addWhitelist(chatId: string, adminToken: string, value: string) {
    return this.request<{ created: boolean }>(`/api/v1/chats/${chatId}/whitelist`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ type: "user", value }),
    });
  }

  deleteWhitelist(chatId: string, adminToken: string, value: string) {
    return this.request<{ deleted: number }>(`/api/v1/chats/${chatId}/whitelist?value=${encodeURIComponent(value)}`, {
      method: "DELETE",
      headers: this.adminHeaders(adminToken),
    });
  }

  listBlacklist(chatId: string, adminToken: string) {
    return this.request<ListItem[]>(`/api/v1/chats/${chatId}/blacklist`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  addBlacklist(chatId: string, adminToken: string, value: string) {
    return this.request<{ created: boolean }>(`/api/v1/chats/${chatId}/blacklist`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ type: "word", value }),
    });
  }

  deleteBlacklist(chatId: string, adminToken: string, value: string) {
    return this.request<{ deleted: number }>(`/api/v1/chats/${chatId}/blacklist?value=${encodeURIComponent(value)}`, {
      method: "DELETE",
      headers: this.adminHeaders(adminToken),
    });
  }

  listAudits(chatId: string, adminToken: string, limit = 100) {
    return this.request<AuditRecord[]>(`/api/v1/chats/${chatId}/audits?limit=${limit}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  listEnforcements(chatId: string, adminToken: string, limit = 100) {
    return this.request<EnforcementRecord[]>(`/api/v1/chats/${chatId}/enforcements?limit=${limit}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  listAppeals(chatId: string, adminToken: string) {
    return this.request<AppealRecord[]>(`/api/v1/chats/${chatId}/appeals`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  rollback(adminToken: string, enforcementId: number) {
    return this.request<{ reason: string }>(`/api/v1/enforcements/${enforcementId}/rollback`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
    });
  }
}
