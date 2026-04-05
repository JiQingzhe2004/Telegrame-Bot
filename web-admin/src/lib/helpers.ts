import dayjs from "dayjs";
import type { AdminActionResult, ApiError } from "@/lib/api";

export function formatTime(value?: string | null): string {
  if (!value) return "-";
  return dayjs(value).format("YYYY-MM-DD HH:mm:ss");
}

export function getErrorMessage(error: unknown, fallback = "请求失败"): string {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (typeof error === "object" && error !== null) {
    const maybeApi = error as Partial<ApiError>;
    if (maybeApi.message) return maybeApi.message;
  }
  return fallback;
}

export function readStorage(key: string, fallback = ""): string {
  const value = localStorage.getItem(key);
  return value ?? fallback;
}

export function writeStorage(key: string, value: string): void {
  localStorage.setItem(key, value);
}

const reasonMap: Record<string, string> = {
  applied: "已执行",
  ok: "查询成功",
  missing_permission: "机器人缺少必要管理员权限",
  unsupported_action: "当前动作不受支持",
  invalid_target: "目标参数无效",
  target_not_found: "目标不存在",
  protected_target_bot: "受保护目标：机器人账号不允许执行该操作",
  protected_target_admin: "受保护目标：群主或管理员不允许执行该操作",
  protected_target_whitelist: "受保护目标：白名单成员不允许执行该操作",
  forbidden: "操作被 Telegram 拒绝",
  bad_request: "请求参数错误",
  timeout: "请求超时",
};

const permissionMap: Record<string, string> = {
  can_change_info: "修改群资料",
  can_delete_messages: "删除消息",
  can_restrict_members: "限制成员（禁言/解禁）",
  can_ban_users: "封禁用户",
  can_invite_users: "邀请用户",
  can_pin_messages: "置顶消息",
  can_promote_members: "管理管理员（提权/降权）",
  can_manage_video_chats: "管理视频聊天",
  can_manage_chat: "管理聊天",
  can_post_stories: "发布动态",
  can_edit_stories: "编辑动态",
  can_delete_stories: "删除动态",
};

export function translateReason(reason?: string | null): string {
  if (!reason) return "操作未完成，请检查权限与参数";
  return reasonMap[reason] ?? reason;
}

export function translatePermission(permission: string): string {
  return permissionMap[permission] ?? permission;
}

export function translateChatMemberStatus(status?: string | null): string {
  const key = (status ?? "").toLowerCase();
  const map: Record<string, string> = {
    creator: "群主",
    owner: "群主",
    administrator: "管理员",
    member: "正常",
    restricted: "禁言/受限",
    kicked: "已封禁",
    banned: "已封禁",
    left: "已退群",
    unknown: "未知",
  };
  return map[key] ?? status ?? "未知";
}

export function formatAdminActionResult(result: AdminActionResult): string {
  const translatedReason = translateReason(result.reason);
  const missing = result.permission_ok ? [] : (result.permission_required ?? []).map(translatePermission);
  if (missing.length > 0) {
    return `${translatedReason}；缺少权限：${missing.join("、")}`;
  }
  return translatedReason;
}

export function buildPermissionCheck(capabilities?: Record<string, boolean>) {
  const entries = Object.entries(capabilities ?? {});
  const missing = entries.filter(([, ok]) => !ok).map(([name]) => name);
  const missingZh = missing.map(translatePermission);
  return {
    missing,
    missingZh,
    allGood: missing.length === 0,
  };
}
