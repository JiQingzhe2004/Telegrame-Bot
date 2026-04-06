export type ChatSettings = {
  chat_id: number;
  chat_enabled: boolean;
  mode: "strict" | "balanced" | "relaxed";
  ai_enabled: boolean;
  ai_threshold: number;
  allow_admin_self_test: boolean;
  action_policy: string;
  rate_limit_policy: string;
  language: string;
  level3_mute_seconds: number;
  points_enabled: boolean;
  points_message_reward: number;
  points_message_cooldown_seconds: number;
  points_daily_cap: number;
  points_transfer_enabled: boolean;
  points_transfer_min_amount: number;
  points_transfer_daily_limit: number;
  points_checkin_base_reward: number;
  points_checkin_streak_bonus: number;
  points_checkin_streak_cap: number;
  hongbao_template: string;
};

export type ChatPointsConfig = Pick<
  ChatSettings,
  | "points_enabled"
  | "points_message_reward"
  | "points_message_cooldown_seconds"
  | "points_daily_cap"
  | "points_transfer_enabled"
  | "points_transfer_min_amount"
  | "points_transfer_daily_limit"
  | "points_checkin_base_reward"
  | "points_checkin_streak_bonus"
  | "points_checkin_streak_cap"
  | "hongbao_template"
>;

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
  state_store_mode: "memory" | "redis";
  state_store_source: "runtime_config" | "env" | "fallback";
  backend_version: string;
};

export type RuntimeConfigPublic = {
  bot_token: string;
  openai_api_key: string;
  openai_base_url: string;
  run_mode: "polling" | "webhook";
  webhook_public_url: string;
  webhook_path: string;
  redis_url: string;
  redis_namespace: string;
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
  has_redis_url: boolean;
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
  is_bot: boolean;
  is_whitelisted: boolean;
  last_message_at: string | null;
  strike_score: number;
  current_status: string | null;
  current_status_until_date: string | null;
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

export type VerificationQuestionGenerateResult = {
  model: string;
  count: number;
  items: VerificationQuestion[];
};

export type PointsBalance = {
  chat_id: number;
  user_id: number;
  balance: number;
  total_earned: number;
  total_spent: number;
  last_changed_at: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
};

export type PointsLedgerEntry = {
  id: number;
  chat_id: number;
  user_id: number;
  counterparty_user_id: number | null;
  change_amount: number;
  balance_after: number;
  event_type: string;
  reason: string | null;
  operator: string;
  created_at: string;
};

export type PointsCheckinState = {
  chat_id: number;
  user_id: number;
  streak_days: number;
  last_checkin_date: string | null;
  created_at: string;
  updated_at: string;
};

export type PointsTaskDefinition = {
  id: number;
  chat_id: number;
  task_key: string;
  title: string;
  description: string;
  task_type: string;
  target_value: number;
  reward_points: number;
  period: string;
  enabled: boolean;
  progress_value?: number;
  completed?: boolean;
  reward_claimed?: boolean;
};

export type PointsShopItem = {
  id: number;
  chat_id: number;
  item_key: string;
  title: string;
  description: string;
  item_type: string;
  price_points: number;
  stock: number | null;
  enabled: boolean;
  meta_json: string | null;
  meta?: {
    title_mode?: "fixed" | "custom";
    fixed_title?: string;
    auto_approve?: boolean;
  };
  created_at: string;
  updated_at: string;
};

export type PointsRedemption = {
  id: number;
  chat_id: number;
  user_id: number;
  item_id: number;
  price_points: number;
  status: string;
  reward_payload: string | null;
  item_key?: string | null;
  item_title?: string | null;
  item_type?: string | null;
  payload?: {
    requested_title?: string;
    fixed_title?: string;
    title_mode?: "fixed" | "custom";
    approval_status?: string;
    apply_error?: string;
    applied_title?: string;
  };
  expires_at: string | null;
  created_at: string;
};

export type LotteryPrize = {
  id?: number;
  lottery_id?: number;
  title: string;
  winner_count: number;
  bonus_points?: number;
  sort_order: number;
  created_at?: string;
};

export type LotteryEntry = {
  id: number;
  lottery_id: number;
  chat_id: number;
  user_id: number;
  entry_count: number;
  points_spent: number;
  source: string;
  status: string;
  ledger_id: number | null;
  refund_ledger_id: number | null;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  created_at: string;
  updated_at: string;
};

export type LotteryWinner = {
  id: number;
  lottery_id: number;
  prize_id: number;
  chat_id: number;
  user_id: number;
  prize_title: string;
  sort_order: number;
  entry_count: number;
  snapshot_json: string | null;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  created_at: string;
};

export type LotteryStats = {
  join_records: number;
  unique_users: number;
  total_entry_count: number;
  total_points_spent: number;
  winner_count: number;
};

export type LotteryDetail = {
  id: number;
  chat_id: number;
  title: string;
  description: string | null;
  status: string;
  entry_mode: "free" | "consume_points" | "balance_threshold";
  points_cost: number;
  points_threshold: number;
  allow_multiple_entries: boolean;
  max_entries_per_user: number;
  show_participants: boolean;
  prize_source: "personal_points" | "group_pool";
  starts_at: string;
  entry_deadline_at: string;
  draw_at: string;
  announcement_message_id: number | null;
  created_by: number | null;
  summary_json: string | null;
  canceled_at: string | null;
  drawn_at: string | null;
  created_at: string;
  updated_at: string;
  prizes: LotteryPrize[];
  stats: LotteryStats;
  winners: LotteryWinner[];
};

export type LotteryPayload = {
  title: string;
  description: string;
  entry_mode: "free" | "consume_points" | "balance_threshold";
  points_cost: number;
  points_threshold: number;
  allow_multiple_entries: boolean;
  max_entries_per_user: number;
  show_participants: boolean;
  prize_source: "personal_points" | "group_pool";
  starts_at: string;
  entry_deadline_at: string;
  draw_at: string;
  created_by?: number | null;
  prizes: LotteryPrize[];
};

export type PointsPacket = {
  id: number;
  chat_id: number;
  sender_user_id: number;
  total_amount: number;
  packet_count: number;
  split_mode: "equal" | "random";
  blessing: string | null;
  status: string;
  claimed_amount: number;
  claimed_count: number;
  remaining_amount: number;
  remaining_count: number;
  expires_at: string;
  message_id: number | null;
  created_at: string;
  updated_at: string;
};

export type PointsPacketClaim = {
  id: number;
  packet_id: number;
  chat_id: number;
  receiver_user_id: number;
  amount: number;
  ledger_id: number | null;
  claimed_at: string;
  username?: string | null;
  first_name?: string | null;
  last_name?: string | null;
};

export type PointsPoolBalance = {
  chat_id: number;
  balance: number;
  updated_at: string | null;
};

export type PointsPoolLedgerEntry = {
  id: number;
  chat_id: number;
  change_amount: number;
  balance_after: number;
  event_type: string;
  operator: string;
  reason: string | null;
  related_packet_id: number | null;
  related_lottery_id: number | null;
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
        | "redis_url"
        | "redis_namespace"
      >
    >,
  ) {
    return this.request<{ runtime_config: RuntimeConfigPublic; state: RuntimeState }>("/api/v1/runtime/config", {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  syncTelegramCommands(adminToken: string) {
    return this.request<{ synced: boolean }>("/api/v1/runtime/telegram/commands/sync", {
      method: "POST",
      headers: this.adminHeaders(adminToken),
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

  getPointsConfig(chatId: string, adminToken: string) {
    return this.request<ChatPointsConfig>(`/api/v1/chats/${chatId}/points/config`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  updatePointsConfig(chatId: string, adminToken: string, payload: Partial<ChatPointsConfig>) {
    return this.request<ChatPointsConfig>(`/api/v1/chats/${chatId}/points/config`, {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  getPointsBalance(chatId: string, adminToken: string, userId: string) {
    return this.request<PointsBalance>(`/api/v1/chats/${chatId}/points/balance/${userId}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  getPointsLeaderboard(chatId: string, adminToken: string, limit = 20) {
    return this.request<PointsBalance[]>(`/api/v1/chats/${chatId}/points/leaderboard?limit=${limit}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  getPointsLedger(chatId: string, adminToken: string, limit = 100, userId?: string) {
    const query = userId ? `?limit=${limit}&user_id=${encodeURIComponent(userId)}` : `?limit=${limit}`;
    return this.request<PointsLedgerEntry[]>(`/api/v1/chats/${chatId}/points/ledger${query}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  adjustPoints(chatId: string, adminToken: string, payload: { user_id: string; amount: number; reason?: string }) {
    return this.request<PointsLedgerEntry>(`/api/v1/chats/${chatId}/points/adjust`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  getPointsCheckinState(chatId: string, adminToken: string, userId: string) {
    return this.request<PointsCheckinState>(`/api/v1/chats/${chatId}/points/checkin/state?user_id=${encodeURIComponent(userId)}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  checkinUser(chatId: string, adminToken: string, userId: string) {
    return this.request<{ reward_points: number; streak_days: number; balance_after: number }>(`/api/v1/chats/${chatId}/points/checkin`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ user_id: userId }),
    });
  }

  getPointsTasks(chatId: string, adminToken: string, userId?: string) {
    const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    return this.request<PointsTaskDefinition[]>(`/api/v1/chats/${chatId}/points/tasks${query}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  getPointsTaskConfig(chatId: string, adminToken: string) {
    return this.request<PointsTaskDefinition[]>(`/api/v1/chats/${chatId}/points/tasks/config`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  updatePointsTaskConfig(chatId: string, adminToken: string, items: PointsTaskDefinition[]) {
    return this.request<PointsTaskDefinition[]>(`/api/v1/chats/${chatId}/points/tasks/config`, {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ items }),
    });
  }

  getPointsShop(chatId: string, adminToken: string) {
    return this.request<PointsShopItem[]>(`/api/v1/chats/${chatId}/points/shop`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  updatePointsShop(chatId: string, adminToken: string, items: PointsShopItem[]) {
    return this.request<PointsShopItem[]>(`/api/v1/chats/${chatId}/points/shop`, {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ items }),
    });
  }

  redeemPointsItem(chatId: string, adminToken: string, payload: { user_id: string; item_key: string }) {
    return this.request<{ redemption: PointsRedemption; balance_after: number; item: PointsShopItem }>(`/api/v1/chats/${chatId}/points/redeem`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  getPointsRedemptions(chatId: string, adminToken: string, userId?: string) {
    const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    return this.request<PointsRedemption[]>(`/api/v1/chats/${chatId}/points/redemptions${query}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  getPointsPackets(chatId: string, adminToken: string) {
    return this.request<PointsPacket[]>(`/api/v1/chats/${chatId}/points/packets`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  getPointsPacket(chatId: string, adminToken: string, packetId: number) {
    return this.request<PointsPacket & { claims: PointsPacketClaim[] }>(`/api/v1/chats/${chatId}/points/packets/${packetId}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  createPointsPacket(
    chatId: string,
    adminToken: string,
    payload: { sender_user_id: number; total_amount: number; packet_count: number; split_mode: "equal" | "random"; blessing?: string },
  ) {
    return this.request<{ packet: PointsPacket; sender_balance_after: number; ledger_id: number }>(`/api/v1/chats/${chatId}/points/packets`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  getPointsPool(chatId: string, adminToken: string) {
    return this.request<PointsPoolBalance>(`/api/v1/chats/${chatId}/points/pool`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  getPointsPoolLedger(chatId: string, adminToken: string, limit = 100) {
    return this.request<PointsPoolLedgerEntry[]>(`/api/v1/chats/${chatId}/points/pool/ledger?limit=${limit}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  adjustPointsPool(chatId: string, adminToken: string, payload: { amount: number; reason: string }) {
    return this.request<PointsPoolLedgerEntry>(`/api/v1/chats/${chatId}/points/pool/adjust`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  updatePointsRedemptionStatus(chatId: string, adminToken: string, redemptionId: number, status: string) {
    return this.request<PointsRedemption>(`/api/v1/chats/${chatId}/points/redemptions/${redemptionId}/status`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({ status }),
    });
  }

  listLotteries(chatId: string, adminToken: string) {
    return this.request<LotteryDetail[]>(`/api/v1/chats/${chatId}/lotteries`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  getLottery(chatId: string, adminToken: string, lotteryId: number) {
    return this.request<LotteryDetail>(`/api/v1/chats/${chatId}/lotteries/${lotteryId}`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  createLottery(chatId: string, adminToken: string, payload: LotteryPayload) {
    return this.request<LotteryDetail>(`/api/v1/chats/${chatId}/lotteries`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  updateLottery(chatId: string, adminToken: string, lotteryId: number, payload: LotteryPayload) {
    return this.request<LotteryDetail>(`/api/v1/chats/${chatId}/lotteries/${lotteryId}`, {
      method: "PUT",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
    });
  }

  getLotteryEntries(chatId: string, adminToken: string, lotteryId: number) {
    return this.request<LotteryEntry[]>(`/api/v1/chats/${chatId}/lotteries/${lotteryId}/entries`, {
      headers: this.adminHeaders(adminToken),
    });
  }

  cancelLottery(chatId: string, adminToken: string, lotteryId: number) {
    return this.request<LotteryDetail>(`/api/v1/chats/${chatId}/lotteries/${lotteryId}/cancel`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({}),
    });
  }

  drawLottery(chatId: string, adminToken: string, lotteryId: number) {
    return this.request<LotteryDetail>(`/api/v1/chats/${chatId}/lotteries/${lotteryId}/draw`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify({}),
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

  generateVerificationQuestions(
    chatId: string,
    adminToken: string,
    payload: { scope: "chat" | "global"; count: number; topic_hint?: string },
  ) {
    return this.request<VerificationQuestionGenerateResult>(`/api/v1/chats/${chatId}/verification/questions/generate`, {
      method: "POST",
      headers: this.adminHeaders(adminToken),
      body: JSON.stringify(payload),
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

  adminKickMember(chatId: string, adminToken: string, userId: string) {
    return this.request<AdminActionResult>(`/api/v1/chats/${chatId}/admin/members/${userId}/kick`, {
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
