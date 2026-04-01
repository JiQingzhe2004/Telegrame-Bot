export type ChatSettings = {
  chat_id: number;
  mode: "strict" | "balanced" | "relaxed";
  ai_enabled: boolean;
  ai_threshold: number;
  allow_admin_self_test: boolean;
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
  join_verification_question_type: "button" | "quiz";
  join_verification_max_attempts: number;
  join_verification_whitelist_bypass: boolean;
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
  ai_status: "skipped" | "success" | "failed";
  ai_error: string | null;
  ai_model: string | null;
  final_level: number;
  confidence: number;
  created_at: string;
};

export type ModerationAiTestResult = {
  chat_ai_enabled: boolean;
  model: string | null;
  category: string;
  level: number;
  confidence: number;
  suggested_action: string;
  reasons: string[];
  latency_ms: number;
};

export type WelcomeAiTestResult = {
  join_welcome_enabled: boolean;
  join_welcome_use_ai: boolean;
  model: string;
  text: string;
  template: string;
  latency_ms: number;
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

export type VerificationQuestion = {
  id: number;
  chat_id: number | null;
  scope: "chat" | "global";
  question: string;
  options: string[];
  answer_index: number;
  answer_text: string | null;
  created_at: string;
};

export class ApiError extends Error {
  status: number;
  code: string;
  detail?: unknown;
  hint?: string;

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
    let resp: Response;
    try {
      resp = await fetch(`${this.baseUrl}${path}`, init);
    } catch (err) {
      // 浏览器层面的网络失败（DNS/端口不通/HTTPS 握手失败/混合内容/CORS 等）
      const e = new ApiError({
        message: "网络请求失败（无法连接后端）",
        status: 0,
        code: "network_error",
        detail: err,
      });
      e.hint =
        "常见原因：\n" +
        "- 访问的是 https 页面，但 API 地址填了 http（会被浏览器拦截，表现为 Failed to fetch）\n" +
        "- 源站未开放 80/443/8080/8443 等端口，或防火墙拦截\n" +
        "- 开了 Cloudflare 橙云但回源端口不受支持（例如直接暴露 10010）\n" +
        "自检：在服务器上访问 /healthz，或临时用 http://域名:端口/healthz 验证后端是否可达。";
      throw e;
    }
    const contentType = resp.headers.get("content-type") ?? "";
    const maybeJson = contentType.includes("application/json");
    const payload = maybeJson ? await resp.json() : await resp.text();

    // 有些网关错误会返回 HTML（例如 Cloudflare 502），这时给更明确的提示。
    if (typeof payload === "string") {
      const text = payload.trim();
      const looksLikeHtml = text.startsWith("<!DOCTYPE html") || text.startsWith("<html") || text.includes("<head>");
      const looksLikeCloudflare = text.toLowerCase().includes("cloudflare") && text.toLowerCase().includes("error code");
      if (looksLikeHtml && looksLikeCloudflare) {
        const e = new ApiError({
          message: `网关错误（可能是 Cloudflare 回源失败，HTTP ${resp.status || "?"}）`,
          status: resp.status,
          code: "cloudflare_gateway_error",
          detail: text.slice(0, 2000),
        });
        e.hint =
          "这通常不是后端接口逻辑报错，而是 Cloudflare 连接不到源站。\n" +
          "常见原因：源站只开了自定义端口（例如 10010），Cloudflare 回源端口不支持；或源站 80/443 未正确反代。\n" +
          "修复建议：\n" +
          "- 让外网入口走 80/443/8080/8443，再反代到 10010\n" +
          "- 或临时灰云（DNS only）直连排障";
        throw e;
      }
    }

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
      const e = new ApiError({ message, status: resp.status, code, detail });
      if (resp.status === 502 && typeof payload === "string" && payload.trim().startsWith("<!DOCTYPE html")) {
        e.hint =
          "收到的是 HTML 网关错误页，说明请求可能没到后端（反代/回源失败）。\n" +
          "建议先访问 /healthz 确认源站可达，然后检查反代端口是否为 80/443/8080/8443。";
      }
      throw e;
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
        | "join_verification_question_type"
        | "join_verification_max_attempts"
        | "join_verification_whitelist_bypass"
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

  listVerificationQuestions(chatId: string, adminToken: string, includeGlobal = true) {
    return this.request<VerificationQuestion[]>(
      `/api/v1/chats/${chatId}/verification/questions?include_global=${includeGlobal ? 1 : 0}`,
      {
        headers: this.adminHeaders(adminToken),
      },
    );
  }

  createVerificationQuestion(
    chatId: string,
    adminToken: string,
    payload: { scope: "chat" | "global"; question: string; options: string[]; answer_index: number },
  ) {
    return this.request<VerificationQuestion>(`/api/v1/chats/${chatId}/verification/questions`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  updateVerificationQuestion(
    chatId: string,
    adminToken: string,
    questionId: number,
    payload: { scope: "chat" | "global"; question: string; options: string[]; answer_index: number },
  ) {
    return this.request<VerificationQuestion>(`/api/v1/chats/${chatId}/verification/questions/${questionId}`, {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  deleteVerificationQuestion(chatId: string, adminToken: string, questionId: number) {
    return this.request<{ deleted: number }>(`/api/v1/chats/${chatId}/verification/questions/${questionId}`, {
      method: "DELETE",
      headers: this.adminHeaders(adminToken),
    });
  }

  listAudits(chatId: string, adminToken: string, limit = 100) {
    return this.request<AuditRecord[]>(`/api/v1/chats/${chatId}/audits?limit=${limit}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  testModerationAi(chatId: string, adminToken: string, text: string) {
    return this.request<ModerationAiTestResult>(`/api/v1/chats/${chatId}/ai-test/moderation`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ text }),
    });
  }

  testWelcomeAi(chatId: string, adminToken: string, userDisplayName: string) {
    return this.request<WelcomeAiTestResult>(`/api/v1/chats/${chatId}/ai-test/welcome`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ user_display_name: userDisplayName }),
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
