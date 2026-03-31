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
  backend_version: string;
};

export type RuntimeConfigPublic = {
  bot_token: string;
  openai_api_key: string;
  openai_base_url: string;
  run_mode: "polling" | "webhook";
  webhook_public_url: string;
  webhook_path: string;
  admin_api_token: string;
  admin_api_token_hash: string;
  default_mode: string;
  default_ai_enabled: boolean;
  default_ai_threshold: number;
  default_action_policy: string;
  default_rate_limit_policy: string;
  default_language: string;
  default_level3_mute_seconds: number;
  ai_low_risk_model: string;
  ai_high_risk_model: string;
  ai_timeout_seconds: number;
  join_verification_enabled: boolean;
  join_verification_timeout_seconds: number;
  join_welcome_enabled: boolean;
  join_welcome_use_ai: boolean;
  join_welcome_template: string;
  has_admin_api_token: boolean;
};

export type SetupState = {
  state: "setup" | "active";
  config_complete: boolean;
  backend_version: string;
  runtime_config: Record<string, unknown>;
};

export type AdminSession = {
  authenticated: boolean;
  backend_version: string;
  runtime_state: RuntimeState;
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

export type KnownChat = {
  chat_id: number;
  title: string | null;
  type: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type AdminActionResult = {
  action_supported: boolean;
  permission_required: string[];
  permission_ok: boolean;
  applied: boolean;
  reason: string;
  telegram_error_code?: number | null;
  data?: Record<string, unknown> | null;
};

export type AdminOverview = {
  chat: {
    id: number;
    type: string;
    title: string | null;
    description: string | null;
  };
  member_count: number;
  administrators: Array<{
    user_id: number;
    username: string | null;
    full_name: string;
    status: string;
    custom_title: string | null;
  }>;
  capabilities: Record<string, boolean>;
};

export type ChatMemberBrief = {
  user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  last_message_at: string | null;
  strike_score: number;
};

export class ApiError extends Error {
  status: number;
  code: string;
  detail?: unknown;

  constructor(params: { message: string; status: number; code?: string; detail?: unknown }) {
    super(params.message);
    this.name = "ApiError";
    this.status = params.status;
    this.code = params.code ?? "api_error";
    this.detail = params.detail;
  }
}

export class ApiClient {
  constructor(private readonly baseUrl: string) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`, init);
    const contentType = resp.headers.get("content-type") ?? "";
    const maybeJson = contentType.includes("application/json");
    const payload = maybeJson ? await resp.json() : await resp.text();

    if (!resp.ok) {
      let message = `HTTP ${resp.status}`;
      let code = "http_error";
      let detail: unknown = payload;
      if (maybeJson && payload && typeof payload === "object") {
        const dataObj = payload as Record<string, unknown>;
        if (typeof dataObj.detail === "string") {
          message = dataObj.detail;
          code = String(dataObj.detail);
          detail = dataObj;
        } else if (typeof dataObj.error === "string") {
          message = dataObj.error;
          code = "api_envelope_error";
        }
      } else if (typeof payload === "string" && payload.trim()) {
        message = payload;
      }
      throw new ApiError({ message, status: resp.status, code, detail });
    }

    const envelope = payload as ApiEnvelope<T>;
    if (!envelope.ok) {
      throw new ApiError({
        message: envelope.error ?? "Unknown API error",
        status: resp.status,
        code: "api_envelope_error",
        detail: envelope,
      });
    }
    return envelope.data;
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

  login(adminToken: string) {
    return this.request<AdminSession>("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ admin_token: adminToken }),
    });
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

  getRuntimeConfig(adminToken: string) {
    return this.request<RuntimeConfigPublic>("/api/v1/runtime/config", {
      headers: this.adminHeaders(adminToken),
    });
  }

  updateRuntimeConfig(
    adminToken: string,
    payload: Partial<
      Pick<
        RuntimeConfigPublic,
        | "openai_api_key"
        | "openai_base_url"
        | "ai_low_risk_model"
        | "ai_high_risk_model"
        | "ai_timeout_seconds"
        | "join_verification_enabled"
        | "join_verification_timeout_seconds"
        | "join_welcome_enabled"
        | "join_welcome_use_ai"
        | "join_welcome_template"
        | "run_mode"
        | "webhook_public_url"
        | "webhook_path"
      >
    >,
  ) {
    return this.request<{ runtime_config: RuntimeConfigPublic; state: RuntimeState }>("/api/v1/runtime/config", {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  listChats(adminToken: string, limit = 200) {
    return this.request<KnownChat[]>(`/api/v1/chats?limit=${limit}`, {
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

  adminOverview(chatId: string, adminToken: string) {
    return this.request<AdminOverview>(`/api/v1/chats/${chatId}/admin/overview`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  adminListMembers(chatId: string, adminToken: string, limit = 200, q = "") {
    return this.request<ChatMemberBrief[]>(`/api/v1/chats/${chatId}/admin/members?limit=${limit}&q=${encodeURIComponent(q)}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  adminGetMember(chatId: string, adminToken: string, userId: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/members/${userId}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  adminUpdateProfile(chatId: string, adminToken: string, payload: { title?: string; description?: string }) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/profile`, {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  adminDeleteMessage(chatId: string, adminToken: string, messageId: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/messages/${messageId}/delete`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
    });
  }

  adminPinMessage(chatId: string, adminToken: string, messageId: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/messages/${messageId}/pin`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
    });
  }

  adminUnpinMessage(chatId: string, adminToken: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/messages/unpin`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
    });
  }

  adminMuteMember(chatId: string, adminToken: string, userId: string, durationSeconds: number) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/members/${userId}/mute`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ duration_seconds: durationSeconds }),
    });
  }

  adminUnmuteMember(chatId: string, adminToken: string, userId: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/members/${userId}/unmute`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
    });
  }

  adminBanMember(chatId: string, adminToken: string, userId: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/members/${userId}/ban`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
    });
  }

  adminUnbanMember(chatId: string, adminToken: string, userId: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/members/${userId}/unban`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
    });
  }

  adminCreateInvite(chatId: string, adminToken: string, name?: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/invite-links/create`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ name }),
    });
  }

  adminRevokeInvite(chatId: string, adminToken: string, inviteLink: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/invite-links/revoke`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ invite_link: inviteLink }),
    });
  }

  adminPromote(chatId: string, adminToken: string, userId: string, payload: Record<string, boolean>) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/admins/${userId}/promote`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  adminDemote(chatId: string, adminToken: string, userId: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/admins/${userId}/demote`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
    });
  }

  adminSetTitle(chatId: string, adminToken: string, userId: string, title: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/admins/${userId}/title`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ title }),
    });
  }
}
