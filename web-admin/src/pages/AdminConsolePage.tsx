import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  App as AntApp,
  Badge,
  Button,
  Input,
  Layout,
  Menu,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import {
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
import { getErrorMessage, readStorage, writeStorage, formatTime } from "@/lib/helpers";
import { queryKeys } from "@/lib/queryKeys";
import { RunOverviewPanel } from "@/components/admin/RunOverviewPanel";
import { GroupManagePanel } from "@/components/admin/GroupManagePanel";
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

  useEffect(() => writeStorage("bot_admin_token", adminToken), [adminToken]);
  useEffect(() => writeStorage("bot_chat_id", chatId), [chatId]);
  useEffect(() => writeStorage("bot_member_keyword", memberKeyword), [memberKeyword]);
  useEffect(() => writeStorage("bot_base_url", baseUrl), [baseUrl]);

  const authed = Boolean(adminToken);
  const chatReady = Boolean(chatId);

  const statusQuery = useQuery({
    queryKey: queryKeys.status(adminToken),
    queryFn: () => api.getStatus(adminToken),
    enabled: authed,
  });

  const chatsQuery = useQuery({
    queryKey: queryKeys.chats(adminToken),
    queryFn: () => api.listChats(adminToken),
    enabled: authed,
  });

  useEffect(() => {
    if (!chatId && chatsQuery.data?.length) {
      setChatId(String(chatsQuery.data[0].chat_id));
    }
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
    membersQuery.isLoading;

  useEffect(() => {
    if (
      statusQuery.data ||
      chatsQuery.data ||
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
        notification.warning({
          message: "动作未完全执行",
          description: result.reason || "请检查机器人权限",
        });
      } else {
        message.success(result.reason || successText);
      }
      await refreshAll();
    } catch (error) {
      message.error(getErrorMessage(error));
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
    setTargetUser: () => undefined,
  };

  const bundle: AdminDataBundle = {
    status: statusQuery.data,
    knownChats: chatsQuery.data ?? [],
    settings: settingsQuery.data,
    overview: overviewQuery.data,
    members: membersQuery.data ?? [],
    whitelist: whitelistQuery.data ?? [],
    blacklist: blacklistQuery.data ?? [],
    audits: (auditsQuery.data ?? []).filter((item) => item.rule_hit.includes(globalSearch) || !globalSearch),
    enforcements: (enforcementsQuery.data ?? []).filter((item) => item.reason.includes(globalSearch) || !globalSearch),
    appeals: (appealsQuery.data ?? []).filter((item) => item.message.includes(globalSearch) || !globalSearch),
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
    if (!adminToken) {
      return <Alert type="warning" showIcon message="请先在系统设置中填写管理令牌" />;
    }
    if (!chatId) {
      return <Alert type="info" showIcon message="请先选择 Chat ID（可点击系统设置里的自动获取）" />;
    }
    switch (menuKey) {
      case "overview":
        return <RunOverviewPanel runtimeState={runtimeState} chatId={chatId} data={bundle} />;
      case "group":
        return (
          <GroupManagePanel
            chatId={chatId}
            adminToken={adminToken}
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
      case "policy":
        return <PolicyConfigPanel data={bundle} actions={actions} />;
      case "lists":
        return <ListManagePanel data={bundle} actions={actions} />;
      case "audit":
        return <AuditCenterPanel data={bundle} />;
      case "enforcement":
        return <EnforcementPanel data={bundle} actions={actions} />;
      case "appeals":
        return <AppealsPanel data={bundle} />;
      case "system":
        return (
          <SystemSettingsPanel
            baseUrl={baseUrl}
            setBaseUrl={onBaseUrlChange}
            adminToken={adminToken}
            setAdminToken={setAdminToken}
            chatId={chatId}
            setChatId={setChatId}
            knownChats={bundle.knownChats}
            onReloadChats={async () => {
              await chatsQuery.refetch();
              if (!(chatsQuery.data?.length ?? 0)) {
                message.info("暂无群记录，请在群里 @机器人 发一条消息");
              }
            }}
            runtimeState={runtimeState}
            lastSyncText={lastSyncAt ? formatTime(lastSyncAt.toISOString()) : "-"}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider width={240} theme="light">
        <div style={{ padding: 16, borderBottom: "1px solid #f0f0f0" }}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            Telegram 管理后台
          </Typography.Title>
          <Typography.Text type="secondary">企业聚合控制台</Typography.Text>
        </div>
        <Menu mode="inline" selectedKeys={[menuKey]} items={menuItems as unknown as never[]} onClick={(e) => setMenuKey(e.key as MenuKey)} />
      </Layout.Sider>
      <Layout>
        <Layout.Header style={{ background: "#fff", borderBottom: "1px solid #f0f0f0", paddingInline: 20 }}>
          <Space style={{ width: "100%", justifyContent: "space-between" }}>
            <Space>
              <Badge status={runtimeState === "active" ? "success" : "default"} text={runtimeState.toUpperCase()} />
              <Tag color="blue">{chatId || "未选择 Chat"}</Tag>
              <Typography.Text type="secondary">最近同步: {lastSyncAt ? formatTime(lastSyncAt.toISOString()) : "-"}</Typography.Text>
            </Space>
            <Space>
              <Input.Search placeholder="快捷搜索（审计/处置/申诉）" allowClear value={globalSearch} onChange={(e) => setGlobalSearch(e.target.value)} style={{ width: 280 }} />
              <Button onClick={() => void refreshAll()}>手动刷新</Button>
            </Space>
          </Space>
        </Layout.Header>
        <Layout.Content style={{ padding: 20 }}>
          {statusQuery.isError ? (
            <Alert type="error" showIcon message={getErrorMessage(statusQuery.error)} style={{ marginBottom: 16 }} />
          ) : null}
          {isLoading ? <Spin style={{ marginBottom: 16 }} /> : null}
          {renderContent()}
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
