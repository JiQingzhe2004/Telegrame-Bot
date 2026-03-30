import { useEffect, useMemo, useState } from "react";
import { Alert, App as AntApp, Badge, Button, Input, Layout, Menu, Space, Spin, Tag, Typography } from "antd";
import {
  ApiOutlined,
  DashboardOutlined,
  FileSearchOutlined,
  MessageOutlined,
  OrderedListOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiClient, type AdminActionResult } from "@/lib/api";
import {
  buildPermissionCheck,
  formatAdminActionResult,
  formatTime,
  getErrorMessage,
  readStorage,
  translatePermission,
  writeStorage,
} from "@/lib/helpers";
import { queryKeys } from "@/lib/queryKeys";
import { RunOverviewPanel } from "@/components/admin/RunOverviewPanel";
import { GroupManagePanel } from "@/components/admin/GroupManagePanel";
import { AiConfigPanel } from "@/components/admin/AiConfigPanel";
import { PolicyConfigPanel } from "@/components/admin/PolicyConfigPanel";
import { ListManagePanel } from "@/components/admin/ListManagePanel";
import { AuditCenterPanel } from "@/components/admin/AuditCenterPanel";
import { EnforcementPanel } from "@/components/admin/EnforcementPanel";
import { AppealsPanel } from "@/components/admin/AppealsPanel";
import { SystemSettingsPanel } from "@/components/admin/SystemSettingsPanel";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";

const menuItems = [
  { key: "overview", icon: <DashboardOutlined />, label: "运行总览" },
  { key: "group", icon: <TeamOutlined />, label: "群管理" },
  { key: "ai", icon: <ApiOutlined />, label: "AI 配置" },
  { key: "policy", icon: <SafetyCertificateOutlined />, label: "策略配置" },
  { key: "lists", icon: <OrderedListOutlined />, label: "名单管理" },
  { key: "audit", icon: <FileSearchOutlined />, label: "审计中心" },
  { key: "enforcement", icon: <ThunderboltOutlined />, label: "处置记录" },
  { key: "appeals", icon: <MessageOutlined />, label: "申诉与回滚" },
  { key: "system", icon: <SettingOutlined />, label: "系统设置" },
] as const;

type MenuKey = (typeof menuItems)[number]["key"];

type Props = {
  baseUrl: string;
  onBaseUrlChange: (value: string) => void;
  runtimeState: "setup" | "active";
};

export function AdminConsolePage({ baseUrl, onBaseUrlChange, runtimeState }: Props) {
  const { message, notification } = AntApp.useApp();
  const queryClient = useQueryClient();
  const api = useMemo(() => new ApiClient(baseUrl), [baseUrl]);

  const [menuKey, setMenuKey] = useState<MenuKey>("overview");
  const [adminToken, setAdminToken] = useState(readStorage("bot_admin_token"));
  const [chatId, setChatId] = useState(readStorage("bot_chat_id"));
  const [memberKeyword, setMemberKeyword] = useState(readStorage("bot_member_keyword"));
  const [globalSearch, setGlobalSearch] = useState("");
  const [memberAutoRefresh, setMemberAutoRefresh] = useState(true);
  const [lastSyncAt, setLastSyncAt] = useState<Date | null>(null);
  const [permissionChecking, setPermissionChecking] = useState(false);
  const [savingRuntimeConfig, setSavingRuntimeConfig] = useState(false);

  useEffect(() => writeStorage("bot_member_keyword", memberKeyword), [memberKeyword]);

  const authed = Boolean(adminToken);
  const chatReady = Boolean(chatId);

  const statusQuery = useQuery({
    queryKey: queryKeys.status(adminToken),
    queryFn: () => api.getStatus(adminToken),
    enabled: authed,
  });
  const runtimeConfigQuery = useQuery({
    queryKey: queryKeys.runtimeConfig(adminToken),
    queryFn: () => api.getRuntimeConfig(adminToken),
    enabled: authed,
  });
  const chatsQuery = useQuery({
    queryKey: queryKeys.chats(adminToken),
    queryFn: () => api.listChats(adminToken),
    enabled: authed,
  });

  useEffect(() => {
    if (!chatId && chatsQuery.data?.length) setChatId(String(chatsQuery.data[0].chat_id));
  }, [chatId, chatsQuery.data]);

  const settingsQuery = useQuery({
    queryKey: queryKeys.settings(chatId),
    queryFn: () => api.getSettings(chatId, adminToken),
    enabled: authed && chatReady,
  });
  const overviewQuery = useQuery({
    queryKey: queryKeys.overview(chatId),
    queryFn: () => api.adminOverview(chatId, adminToken),
    enabled: authed && chatReady,
  });
  const membersQuery = useQuery({
    queryKey: queryKeys.members(chatId, memberKeyword),
    queryFn: () => api.adminListMembers(chatId, adminToken, 200, memberKeyword),
    enabled: authed && chatReady,
    refetchInterval: menuKey === "group" && memberAutoRefresh ? 5000 : false,
  });
  const whitelistQuery = useQuery({
    queryKey: queryKeys.whitelist(chatId),
    queryFn: () => api.listWhitelist(chatId, adminToken),
    enabled: authed && chatReady,
  });
  const blacklistQuery = useQuery({
    queryKey: queryKeys.blacklist(chatId),
    queryFn: () => api.listBlacklist(chatId, adminToken),
    enabled: authed && chatReady,
  });
  const auditsQuery = useQuery({
    queryKey: queryKeys.audits(chatId),
    queryFn: () => api.listAudits(chatId, adminToken, 100),
    enabled: authed && chatReady,
  });
  const enforcementsQuery = useQuery({
    queryKey: queryKeys.enforcements(chatId),
    queryFn: () => api.listEnforcements(chatId, adminToken, 100),
    enabled: authed && chatReady,
  });
  const appealsQuery = useQuery({
    queryKey: queryKeys.appeals(chatId),
    queryFn: () => api.listAppeals(chatId, adminToken),
    enabled: authed && chatReady,
  });

  const isLoading =
    statusQuery.isLoading ||
    chatsQuery.isLoading ||
    settingsQuery.isLoading ||
    overviewQuery.isLoading ||
    membersQuery.isLoading ||
    runtimeConfigQuery.isLoading;

  useEffect(() => {
    if (
      statusQuery.data ||
      chatsQuery.data ||
      runtimeConfigQuery.data ||
      settingsQuery.data ||
      overviewQuery.data ||
      membersQuery.data ||
      whitelistQuery.data ||
      blacklistQuery.data ||
      auditsQuery.data ||
      enforcementsQuery.data ||
      appealsQuery.data
    ) {
      setLastSyncAt(new Date());
    }
  }, [
    statusQuery.data,
    chatsQuery.data,
    runtimeConfigQuery.data,
    settingsQuery.data,
    overviewQuery.data,
    membersQuery.data,
    whitelistQuery.data,
    blacklistQuery.data,
    auditsQuery.data,
    enforcementsQuery.data,
    appealsQuery.data,
  ]);

  const refreshAll = async () => {
    await queryClient.invalidateQueries();
    await Promise.all([
      statusQuery.refetch(),
      runtimeConfigQuery.refetch(),
      chatsQuery.refetch(),
      settingsQuery.refetch(),
      overviewQuery.refetch(),
      membersQuery.refetch(),
      whitelistQuery.refetch(),
      blacklistQuery.refetch(),
      auditsQuery.refetch(),
      enforcementsQuery.refetch(),
      appealsQuery.refetch(),
    ]);
    message.success("数据已刷新");
  };

  const runAction = async (runner: () => Promise<AdminActionResult>, successText = "操作成功") => {
    try {
      const result = await runner();
      if (!result.applied || !result.permission_ok) {
        notification.warning({ message: "动作未完全执行", description: formatAdminActionResult(result) });
      } else {
        message.success(result.reason ? formatAdminActionResult(result) : successText);
      }
      await refreshAll();
    } catch (error) {
      message.error(getErrorMessage(error));
    }
  };

  const runPermissionCheck = () => {
    setPermissionChecking(true);
    try {
      const report = buildPermissionCheck(overviewQuery.data?.capabilities);
      if (report.allGood) {
        notification.success({ message: "权限自检通过", description: "机器人关键管理员权限完整，可执行常见管理动作。" });
      } else {
        notification.warning({
          message: "权限自检未通过",
          description: `缺少权限：${report.missingZh.join("、")}。请到 Telegram 群管理里给机器人补齐对应权限。`,
          duration: 8,
        });
      }
    } finally {
      setPermissionChecking(false);
    }
  };

  const saveRuntimeConfig = async (payload: {
    openai_api_key?: string;
    openai_base_url?: string;
    ai_low_risk_model: string;
    ai_high_risk_model: string;
    ai_timeout_seconds: number;
    run_mode: "polling" | "webhook";
    webhook_public_url?: string;
    webhook_path?: string;
  }) => {
    setSavingRuntimeConfig(true);
    try {
      await api.updateRuntimeConfig(adminToken, payload);
      message.success("AI 配置已更新并热生效");
      await Promise.all([runtimeConfigQuery.refetch(), statusQuery.refetch()]);
    } catch (error) {
      message.error(getErrorMessage(error));
    } finally {
      setSavingRuntimeConfig(false);
    }
  };

  const actions: AdminActions = {
    refreshAll,
    updateSettings: async (payload) => {
      try {
        await api.updateSettings(chatId, adminToken, payload);
        message.success("策略已更新");
        await settingsQuery.refetch();
      } catch (error) {
        message.error(getErrorMessage(error));
      }
    },
    addWhitelist: async (value) => {
      if (!value.trim()) return;
      try {
        await api.addWhitelist(chatId, adminToken, value.trim());
        message.success("白名单已添加");
        await whitelistQuery.refetch();
      } catch (error) {
        message.error(getErrorMessage(error));
      }
    },
    addBlacklist: async (value) => {
      if (!value.trim()) return;
      try {
        await api.addBlacklist(chatId, adminToken, value.trim());
        message.success("黑名单词已添加");
        await blacklistQuery.refetch();
      } catch (error) {
        message.error(getErrorMessage(error));
      }
    },
    removeWhitelist: async (value) => {
      try {
        await api.deleteWhitelist(chatId, adminToken, value);
        message.success("已移除");
        await whitelistQuery.refetch();
      } catch (error) {
        message.error(getErrorMessage(error));
      }
    },
    removeBlacklist: async (value) => {
      try {
        await api.deleteBlacklist(chatId, adminToken, value);
        message.success("已移除");
        await blacklistQuery.refetch();
      } catch (error) {
        message.error(getErrorMessage(error));
      }
    },
    rollback: async (enforcementId) => {
      try {
        await api.rollback(adminToken, enforcementId);
        message.success(`回滚请求已提交 #${enforcementId}`);
        await enforcementsQuery.refetch();
      } catch (error) {
        message.error(getErrorMessage(error));
      }
    },
    runAction,
  };

  const bundle: AdminDataBundle = {
    status: statusQuery.data,
    knownChats: chatsQuery.data ?? [],
    settings: settingsQuery.data,
    overview: overviewQuery.data,
    members: membersQuery.data ?? [],
    whitelist: whitelistQuery.data ?? [],
    blacklist: blacklistQuery.data ?? [],
    audits: (auditsQuery.data ?? []).filter((item) => !globalSearch || item.rule_hit.includes(globalSearch)),
    enforcements: (enforcementsQuery.data ?? []).filter((item) => !globalSearch || item.reason.includes(globalSearch)),
    appeals: (appealsQuery.data ?? []).filter((item) => !globalSearch || item.message.includes(globalSearch)),
    isLoading,
  };

  const memberActions = {
    mute: (userId: string, duration: number) => api.adminMuteMember(chatId, adminToken, userId, duration),
    unmute: (userId: string) => api.adminUnmuteMember(chatId, adminToken, userId),
    ban: (userId: string) => api.adminBanMember(chatId, adminToken, userId),
    unban: (userId: string) => api.adminUnbanMember(chatId, adminToken, userId),
    deleteMessage: (messageId: string) => api.adminDeleteMessage(chatId, adminToken, messageId),
    pinMessage: (messageId: string) => api.adminPinMessage(chatId, adminToken, messageId),
    unpinMessage: () => api.adminUnpinMessage(chatId, adminToken),
    createInvite: (name: string) => api.adminCreateInvite(chatId, adminToken, name),
    revokeInvite: (inviteLink: string) => api.adminRevokeInvite(chatId, adminToken, inviteLink),
    promote: (userId: string) =>
      api.adminPromote(chatId, adminToken, userId, {
        can_manage_chat: true,
        can_delete_messages: true,
        can_invite_users: true,
        can_restrict_members: true,
        can_pin_messages: true,
        can_manage_video_chats: true,
      }),
    demote: (userId: string) => api.adminDemote(chatId, adminToken, userId),
    setTitle: (userId: string, title: string) => api.adminSetTitle(chatId, adminToken, userId, title),
    updateProfile: (title: string, description: string) => api.adminUpdateProfile(chatId, adminToken, { title, description }),
  };

  const renderContent = () => {
    if (!adminToken) return <Alert type="warning" showIcon message="请先在系统设置中填写管理令牌" />;
    if (!chatId) return <Alert type="info" showIcon message="请先选择 Chat ID（可点击系统设置里的自动获取）" />;

    if (menuKey === "overview") {
      return <RunOverviewPanel runtimeState={runtimeState} chatId={chatId} data={bundle} onPermissionCheck={runPermissionCheck} checking={permissionChecking} />;
    }
    if (menuKey === "group") {
      return (
        <GroupManagePanel
          chatId={chatId}
          data={bundle}
          actions={actions}
          autoRefresh={memberAutoRefresh}
          setAutoRefresh={setMemberAutoRefresh}
          memberKeyword={memberKeyword}
          setMemberKeyword={setMemberKeyword}
          requestMembersRefresh={async () => {
            await membersQuery.refetch();
          }}
          apiActions={memberActions}
        />
      );
    }
    if (menuKey === "ai") {
      return <AiConfigPanel config={runtimeConfigQuery.data} loading={runtimeConfigQuery.isLoading} saving={savingRuntimeConfig} onSave={saveRuntimeConfig} />;
    }
    if (menuKey === "policy") return <PolicyConfigPanel data={bundle} actions={actions} />;
    if (menuKey === "lists") return <ListManagePanel data={bundle} actions={actions} />;
    if (menuKey === "audit") return <AuditCenterPanel data={bundle} />;
    if (menuKey === "enforcement") return <EnforcementPanel data={bundle} actions={actions} />;
    if (menuKey === "appeals") return <AppealsPanel data={bundle} />;
    return (
      <SystemSettingsPanel
        baseUrl={baseUrl}
        adminToken={adminToken}
        chatId={chatId}
        knownChats={bundle.knownChats}
        onReloadChats={async () => {
          const out = await chatsQuery.refetch();
          if (!(out.data?.length ?? 0)) message.info("暂无群记录，请在群里 @机器人 发一条消息");
        }}
        onSaveConnection={(values) => {
          onBaseUrlChange(values.baseUrl);
          setAdminToken(values.adminToken);
          setChatId(values.chatId);
          writeStorage("bot_base_url", values.baseUrl);
          writeStorage("bot_admin_token", values.adminToken);
          writeStorage("bot_chat_id", values.chatId);
          message.success("连接配置已保存");
        }}
        runtimeState={runtimeState}
        lastSyncText={lastSyncAt ? formatTime(lastSyncAt.toISOString()) : "-"}
      />
    );
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider
        width={240}
        theme="light"
        style={{
          overflow: "auto",
          height: "100vh",
          position: "fixed",
          insetInlineStart: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div style={{ padding: 16, borderBottom: "1px solid #f0f0f0" }}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            Telegram 管理后台
          </Typography.Title>
          <Typography.Text type="secondary">企业聚合控制台</Typography.Text>
        </div>
        <Menu mode="inline" selectedKeys={[menuKey]} items={menuItems as unknown as never[]} onClick={(e) => setMenuKey(e.key as MenuKey)} />
      </Layout.Sider>
      <Layout style={{ marginInlineStart: 240 }}>
        <Layout.Header style={{ background: "#fff", borderBottom: "1px solid #f0f0f0", paddingInline: 20 }}>
          <Space style={{ width: "100%", justifyContent: "space-between" }}>
            <Space>
              <Badge status={runtimeState === "active" ? "success" : "default"} text={runtimeState.toUpperCase()} />
              <Tag color="blue">{chatId || "未选择 Chat"}</Tag>
              <Typography.Text type="secondary">最近同步: {lastSyncAt ? formatTime(lastSyncAt.toISOString()) : "-"}</Typography.Text>
              {overviewQuery.data?.capabilities ? (
                (() => {
                  const report = buildPermissionCheck(overviewQuery.data.capabilities);
                  return report.allGood ? (
                    <Tag color="success">权限正常</Tag>
                  ) : (
                    <Tag color="warning">
                      缺权限: {report.missing.slice(0, 1).map(translatePermission).join("、")}
                      {report.missing.length > 1 ? "..." : ""}
                    </Tag>
                  );
                })()
              ) : null}
            </Space>
            <Space>
              <Input.Search
                placeholder="快捷搜索（审计/处置/申诉）"
                allowClear
                value={globalSearch}
                onChange={(e) => setGlobalSearch(e.target.value)}
                style={{ width: 280 }}
              />
              <Button onClick={() => void refreshAll()}>手动刷新</Button>
            </Space>
          </Space>
        </Layout.Header>
        <Layout.Content style={{ padding: 20, minHeight: "calc(100vh - 64px)", overflow: "auto" }}>
          {statusQuery.isError ? <Alert type="error" showIcon message={getErrorMessage(statusQuery.error)} style={{ marginBottom: 16 }} /> : null}
          {isLoading ? <Spin style={{ marginBottom: 16 }} /> : null}
          {renderContent()}
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
