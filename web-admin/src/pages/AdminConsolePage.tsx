import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  LayoutDashboard,
  Info,
  Users,
  Bot,
  Coins,
  ShieldCheck,
  ListOrdered,
  FileSearch,
  Zap,
  MessageSquare,
  Settings,
  RefreshCw,
  Settings2,
  Wifi,
} from "lucide-react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
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
import { GroupInfoPanel } from "@/components/admin/GroupInfoPanel";
import { AiConfigPanel } from "@/components/admin/AiConfigPanel";
import { PolicyConfigPanel } from "@/components/admin/PolicyConfigPanel";
import { PointsPanel } from "@/components/admin/PointsPanel";
import { ListManagePanel } from "@/components/admin/ListManagePanel";
import { AuditCenterPanel } from "@/components/admin/AuditCenterPanel";
import { EnforcementPanel } from "@/components/admin/EnforcementPanel";
import { AppealsPanel } from "@/components/admin/AppealsPanel";
import { SystemSettingsPanel } from "@/components/admin/SystemSettingsPanel";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { AppLayout, type SidebarItem } from "@/components/admin/AppLayout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const menuItems: readonly SidebarItem[] = [
  { key: "overview", icon: LayoutDashboard, label: "运行总览" },
  { key: "group-info", icon: Info, label: "群信息" },
  { key: "group-members", icon: Users, label: "成员管理" },
  { key: "ai", icon: Bot, label: "AI 配置" },
  { key: "policy", icon: ShieldCheck, label: "策略配置" },
  { key: "points", icon: Coins, label: "积分管理" },
  { key: "lists", icon: ListOrdered, label: "名单管理" },
  { key: "audit", icon: FileSearch, label: "审计中心" },
  { key: "enforcement", icon: Zap, label: "处置记录" },
  { key: "appeals", icon: MessageSquare, label: "申诉与回滚" },
  { key: "system", icon: Settings, label: "系统设置" },
] as const;

type MenuKey = (typeof menuItems)[number]["key"];

type Props = {
  baseUrl: string;
  onBaseUrlChange: (value: string) => void;
  runtimeState: "setup" | "active";
  adminToken: string;
  frontendVersion: string;
  backendVersion: string;
  onLogout: () => void;
};

export function AdminConsolePage({
  baseUrl,
  onBaseUrlChange,
  runtimeState,
  adminToken,
  frontendVersion,
  backendVersion,
  onLogout,
}: Props) {
  const api = useMemo(() => new ApiClient(baseUrl), [baseUrl]);

  const [menuKey, setMenuKey] = useState<MenuKey>("overview");
  const [chatId, setChatId] = useState(readStorage("bot_chat_id"));
  const [memberKeyword, setMemberKeyword] = useState(readStorage("bot_member_keyword"));
  const [globalSearch] = useState("");
  const [memberAutoRefresh, setMemberAutoRefresh] = useState(true);
  const [lastSyncAt, setLastSyncAt] = useState<Date | null>(null);
  const [permissionChecking, setPermissionChecking] = useState(false);
  const [savingRuntimeConfig, setSavingRuntimeConfig] = useState(false);
  const [generatingVerificationQuestions, setGeneratingVerificationQuestions] = useState(false);
  const [queriedPointsUserId, setQueriedPointsUserId] = useState("");

  useEffect(() => writeStorage("bot_member_keyword", memberKeyword), [memberKeyword]);

  const authed = Boolean(adminToken);
  const chatReady = Boolean(chatId);
  const keepCurrentChatData = <T,>(previousData: T | undefined, previousQuery?: { queryKey: readonly unknown[] }) =>
    previousQuery?.queryKey[2] === chatId ? previousData : undefined;
  const keepCurrentMembersData = <T,>(previousData: T | undefined, previousQuery?: { queryKey: readonly unknown[] }) =>
    previousQuery?.queryKey[2] === chatId && previousQuery?.queryKey[3] === memberKeyword ? previousData : undefined;

  const statusQuery = useQuery({
    queryKey: queryKeys.status(baseUrl, adminToken),
    queryFn: () => api.getStatus(adminToken),
    enabled: authed,
    placeholderData: keepPreviousData,
    refetchInterval: 15000,
    refetchOnWindowFocus: false,
  });
  const runtimeConfigQuery = useQuery({
    queryKey: queryKeys.runtimeConfig(baseUrl, adminToken),
    queryFn: () => api.getRuntimeConfig(adminToken),
    enabled: authed,
    placeholderData: keepPreviousData,
    refetchInterval: menuKey === "ai" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const chatsQuery = useQuery({
    queryKey: queryKeys.chats(baseUrl, adminToken),
    queryFn: () => api.listChats(adminToken),
    enabled: authed,
    placeholderData: keepPreviousData,
    refetchInterval: !chatId || menuKey === "system" ? 15000 : false,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!chatId && chatsQuery.data?.length) {
      const nextChatId = String(chatsQuery.data[0].chat_id);
      setChatId(nextChatId);
      writeStorage("bot_chat_id", nextChatId);
    }
  }, [chatId, chatsQuery.data]);

  const settingsQuery = useQuery({
    queryKey: queryKeys.settings(baseUrl, chatId, adminToken),
    queryFn: () => api.getSettings(chatId, adminToken),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "policy" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const overviewQuery = useQuery({
    queryKey: queryKeys.overview(baseUrl, chatId, adminToken),
    queryFn: () => api.adminOverview(chatId, adminToken),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "overview" || menuKey === "group-info" || menuKey === "group-members" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const membersQuery = useQuery({
    queryKey: queryKeys.members(baseUrl, chatId, memberKeyword, adminToken),
    queryFn: () => api.adminListMembers(chatId, adminToken, 200, memberKeyword),
    enabled: authed && chatReady,
    placeholderData: keepCurrentMembersData,
    refetchInterval: menuKey === "group-members" && memberAutoRefresh ? 5000 : false,
    refetchOnWindowFocus: false,
  });
  const verificationQuestionsQuery = useQuery({
    queryKey: queryKeys.verificationQuestions(baseUrl, chatId, adminToken),
    queryFn: () => api.listVerificationQuestions(chatId, adminToken),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "ai" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const whitelistQuery = useQuery({
    queryKey: queryKeys.whitelist(baseUrl, chatId, adminToken),
    queryFn: () => api.listWhitelist(chatId, adminToken),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "lists" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const blacklistQuery = useQuery({
    queryKey: queryKeys.blacklist(baseUrl, chatId, adminToken),
    queryFn: () => api.listBlacklist(chatId, adminToken),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "lists" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const pointsConfigQuery = useQuery({
    queryKey: queryKeys.pointsConfig(baseUrl, chatId, adminToken),
    queryFn: () => api.getPointsConfig(chatId, adminToken),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "points" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const pointsLeaderboardQuery = useQuery({
    queryKey: queryKeys.pointsLeaderboard(baseUrl, chatId, adminToken),
    queryFn: () => api.getPointsLeaderboard(chatId, adminToken, 20),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "points" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const pointsLedgerQuery = useQuery({
    queryKey: queryKeys.pointsLedger(baseUrl, chatId, "", adminToken),
    queryFn: () => api.getPointsLedger(chatId, adminToken, 100),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "points" ? 15000 : false,
    refetchOnWindowFocus: false,
  });
  const pointsBalanceQuery = useQuery({
    queryKey: queryKeys.pointsBalance(baseUrl, chatId, queriedPointsUserId, adminToken),
    queryFn: () => api.getPointsBalance(chatId, adminToken, queriedPointsUserId),
    enabled: authed && chatReady && Boolean(queriedPointsUserId),
    refetchOnWindowFocus: false,
  });
  const auditsQuery = useQuery({
    queryKey: queryKeys.audits(baseUrl, chatId, adminToken),
    queryFn: () => api.listAudits(chatId, adminToken, 100),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "audit" ? 5000 : false,
    refetchOnWindowFocus: false,
  });
  const enforcementsQuery = useQuery({
    queryKey: queryKeys.enforcements(baseUrl, chatId, adminToken),
    queryFn: () => api.listEnforcements(chatId, adminToken, 100),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "enforcement" ? 5000 : false,
    refetchOnWindowFocus: false,
  });
  const appealsQuery = useQuery({
    queryKey: queryKeys.appeals(baseUrl, chatId, adminToken),
    queryFn: () => api.listAppeals(chatId, adminToken),
    enabled: authed && chatReady,
    placeholderData: keepCurrentChatData,
    refetchInterval: menuKey === "appeals" ? 10000 : false,
    refetchOnWindowFocus: false,
  });

  const isLoading =
    statusQuery.isLoading ||
    chatsQuery.isLoading ||
    settingsQuery.isLoading ||
    overviewQuery.isLoading ||
    membersQuery.isLoading ||
    verificationQuestionsQuery.isLoading ||
    runtimeConfigQuery.isLoading ||
    pointsConfigQuery.isLoading ||
    pointsLeaderboardQuery.isLoading ||
    pointsLedgerQuery.isLoading;

  useEffect(() => {
    if (
      statusQuery.data ||
      chatsQuery.data ||
      runtimeConfigQuery.data ||
      settingsQuery.data ||
      overviewQuery.data ||
      membersQuery.data ||
      verificationQuestionsQuery.data ||
      whitelistQuery.data ||
      blacklistQuery.data ||
      pointsConfigQuery.data ||
      pointsLeaderboardQuery.data ||
      pointsLedgerQuery.data ||
      pointsBalanceQuery.data ||
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
    verificationQuestionsQuery.data,
    whitelistQuery.data,
    blacklistQuery.data,
    pointsConfigQuery.data,
    pointsLeaderboardQuery.data,
    pointsLedgerQuery.data,
    pointsBalanceQuery.data,
    auditsQuery.data,
    enforcementsQuery.data,
    appealsQuery.data,
  ]);

  const isRefreshing =
    statusQuery.isFetching ||
    runtimeConfigQuery.isFetching ||
    chatsQuery.isFetching ||
    settingsQuery.isFetching ||
    overviewQuery.isFetching ||
    membersQuery.isFetching ||
    verificationQuestionsQuery.isFetching ||
    whitelistQuery.isFetching ||
    blacklistQuery.isFetching ||
    pointsConfigQuery.isFetching ||
    pointsLeaderboardQuery.isFetching ||
    pointsLedgerQuery.isFetching ||
    pointsBalanceQuery.isFetching ||
    auditsQuery.isFetching ||
    enforcementsQuery.isFetching ||
    appealsQuery.isFetching;

  const refreshVisibleData = async () => {
    const tasks: Array<Promise<unknown>> = [statusQuery.refetch(), chatsQuery.refetch()];
    if (menuKey === "ai" || menuKey === "system") {
      tasks.push(runtimeConfigQuery.refetch());
    }
    if (chatReady) {
      tasks.push(settingsQuery.refetch(), overviewQuery.refetch());
      if (menuKey === "ai") tasks.push(verificationQuestionsQuery.refetch());
      if (menuKey === "group-members") tasks.push(membersQuery.refetch());
      if (menuKey === "lists") tasks.push(whitelistQuery.refetch(), blacklistQuery.refetch());
      if (menuKey === "points") tasks.push(pointsConfigQuery.refetch(), pointsLeaderboardQuery.refetch(), pointsLedgerQuery.refetch());
      if (menuKey === "audit") tasks.push(auditsQuery.refetch());
      if (menuKey === "enforcement") tasks.push(enforcementsQuery.refetch());
      if (menuKey === "appeals") tasks.push(appealsQuery.refetch());
    }
    await Promise.all(tasks);
    toast.success("数据已刷新");
  };

  const refreshModerationData = async () => {
    const tasks: Array<Promise<unknown>> = [statusQuery.refetch()];
    if (chatReady) {
      tasks.push(overviewQuery.refetch(), membersQuery.refetch(), auditsQuery.refetch(), enforcementsQuery.refetch(), appealsQuery.refetch());
    }
    await Promise.all(tasks);
  };

  const runAction = async (runner: () => Promise<AdminActionResult>, successText = "操作成功") => {
    try {
      const result = await runner();
      if (!result.applied || !result.permission_ok) {
        toast.warning(formatAdminActionResult(result), { description: "动作未完全执行" });
      } else {
        toast.success(successText || formatAdminActionResult(result));
      }
      await refreshModerationData();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const runPermissionCheck = () => {
    setPermissionChecking(true);
    try {
      const report = buildPermissionCheck(overviewQuery.data?.capabilities);
      if (report.allGood) {
        toast.success("权限自检通过", { description: "机器人关键管理员权限完整，可执行常见管理动作。" });
      } else {
        toast.warning("权限自检未通过", {
          description: `缺少权限：${report.missingZh.join("、")}。请到 Telegram 群管理里给机器人补齐对应权限。`,
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
    join_verification_enabled: boolean;
    join_verification_timeout_seconds: number;
    join_verification_question_type: "button" | "quiz";
    join_verification_max_attempts: number;
    join_verification_whitelist_bypass: boolean;
    join_welcome_enabled: boolean;
    join_welcome_use_ai: boolean;
    join_welcome_template: string;
    run_mode: "polling" | "webhook";
    webhook_public_url?: string;
    webhook_path?: string;
  }) => {
    setSavingRuntimeConfig(true);
    try {
      await api.updateRuntimeConfig(adminToken, payload);
      toast.success("AI 与入群配置已更新并热生效");
      await Promise.all([runtimeConfigQuery.refetch(), statusQuery.refetch()]);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setSavingRuntimeConfig(false);
    }
  };

  const testModerationAi = async (text: string) => {
    if (!chatId) {
      throw new Error("请先选择 Chat");
    }
    return api.testModerationAi(chatId, adminToken, text);
  };

  const testWelcomeAi = async (userDisplayName: string) => {
    if (!chatId) {
      throw new Error("请先选择 Chat");
    }
    return api.testWelcomeAi(chatId, adminToken, userDisplayName);
  };

  const createVerificationQuestion = async (payload: { scope: "chat" | "global"; question: string; options: string[]; answer_index: number }) => {
    if (!chatId) {
      throw new Error("请先选择 Chat");
    }
    try {
      await api.createVerificationQuestion(chatId, adminToken, payload);
      toast.success("验证题已新增");
      await verificationQuestionsQuery.refetch();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const updateVerificationQuestion = async (
    questionId: number,
    payload: { scope: "chat" | "global"; question: string; options: string[]; answer_index: number },
  ) => {
    if (!chatId) {
      throw new Error("请先选择 Chat");
    }
    try {
      await api.updateVerificationQuestion(chatId, adminToken, questionId, payload);
      toast.success("验证题已更新");
      await verificationQuestionsQuery.refetch();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const deleteVerificationQuestion = async (questionId: number) => {
    if (!chatId) {
      throw new Error("请先选择 Chat");
    }
    try {
      await api.deleteVerificationQuestion(chatId, adminToken, questionId);
      toast.success("验证题已删除");
      await verificationQuestionsQuery.refetch();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const generateVerificationQuestions = async (payload: { scope: "chat" | "global"; count: number; topic_hint?: string }) => {
    if (!chatId) {
      throw new Error("请先选择 Chat");
    }
    setGeneratingVerificationQuestions(true);
    try {
      const result = await api.generateVerificationQuestions(chatId, adminToken, payload);
      toast.success(`AI 已生成 ${result.count} 道题`, { description: `模型 ${result.model}` });
      await verificationQuestionsQuery.refetch();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setGeneratingVerificationQuestions(false);
    }
  };

  const reloadChats = async () => {
    const out = await chatsQuery.refetch();
    const nextChatId = out.data?.[0] ? String(out.data[0].chat_id) : "";
    if (!out.data?.length) {
      toast.info("还没有可用群聊。请先把机器人拉进群；若仍未出现，在群里发送一条消息或命令后再试。");
      return;
    }
    if (!chatId && nextChatId) {
      setChatId(nextChatId);
      writeStorage("bot_chat_id", nextChatId);
      toast.success("已自动选中第一个可用群");
      return;
    }
    toast.success("群列表已刷新");
  };

  const actions: AdminActions = {
    refreshAll: refreshVisibleData,
    updateSettings: async (payload) => {
      try {
        await api.updateSettings(chatId, adminToken, payload);
        toast.success("策略已更新");
        await Promise.all([settingsQuery.refetch(), auditsQuery.refetch(), overviewQuery.refetch()]);
      } catch (error) {
        toast.error(getErrorMessage(error));
      }
    },
    addWhitelist: async (value) => {
      if (!value.trim()) return;
      try {
        await api.addWhitelist(chatId, adminToken, value.trim());
        toast.success("白名单已添加");
        await whitelistQuery.refetch();
      } catch (error) {
        toast.error(getErrorMessage(error));
      }
    },
    addBlacklist: async (value) => {
      if (!value.trim()) return;
      try {
        await api.addBlacklist(chatId, adminToken, value.trim());
        toast.success("黑名单词已添加");
        await blacklistQuery.refetch();
      } catch (error) {
        toast.error(getErrorMessage(error));
      }
    },
    removeWhitelist: async (value) => {
      try {
        await api.deleteWhitelist(chatId, adminToken, value);
        toast.success("已移除");
        await whitelistQuery.refetch();
      } catch (error) {
        toast.error(getErrorMessage(error));
      }
    },
    removeBlacklist: async (value) => {
      try {
        await api.deleteBlacklist(chatId, adminToken, value);
        toast.success("已移除");
        await blacklistQuery.refetch();
      } catch (error) {
        toast.error(getErrorMessage(error));
      }
    },
    rollback: async (enforcementId) => {
      try {
        await api.rollback(adminToken, enforcementId);
        toast.success(`回滚请求已提交 #${enforcementId}`);
        await enforcementsQuery.refetch();
      } catch (error) {
        toast.error(getErrorMessage(error));
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
    pointsConfig: pointsConfigQuery.data,
    pointsLeaderboard: pointsLeaderboardQuery.data ?? [],
    pointsLedger: pointsLedgerQuery.data ?? [],
    audits: (auditsQuery.data ?? []).filter((item) => !globalSearch || item.rule_hit.includes(globalSearch)),
    enforcements: (enforcementsQuery.data ?? []).filter((item) => !globalSearch || item.reason.includes(globalSearch)),
    appeals: (appealsQuery.data ?? []).filter((item) => !globalSearch || item.message.includes(globalSearch)),
    isLoading,
  };

  const memberActions = {
    getMember: (userId: string) => api.adminGetMember(chatId, adminToken, userId),
    mute: (userId: string, duration: number) => api.adminMuteMember(chatId, adminToken, userId, duration),
    unmute: (userId: string) => api.adminUnmuteMember(chatId, adminToken, userId),
    ban: (userId: string) => api.adminBanMember(chatId, adminToken, userId),
    kick: (userId: string) => api.adminKickMember(chatId, adminToken, userId),
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
    if (!chatId) {
      return (
        <Alert className="border-sky-200 bg-sky-50 text-sky-900 dark:border-cyan-400/20 dark:bg-cyan-500/10 dark:text-cyan-100">
          <AlertTitle>还没有可用的 Chat</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-3">
            <span>机器人被拉进群后会自动登记该群。若列表还没出现，先点一次“自动获取 Chat”；如果仍没有，就在目标群里发送一条消息或管理员命令后再试。</span>
            <Button size="sm" onClick={() => void reloadChats()}>
              <Wifi className="mr-2 h-4 w-4" />
              自动获取 Chat
            </Button>
            <Button size="sm" variant="outline" onClick={() => setMenuKey("system")}>
              <Settings2 className="mr-2 h-4 w-4" />
              打开系统设置
            </Button>
          </AlertDescription>
        </Alert>
      );
    }

    if (menuKey === "overview") {
      return <RunOverviewPanel runtimeState={runtimeState} chatId={chatId} data={bundle} onPermissionCheck={runPermissionCheck} checking={permissionChecking} />;
    }
    if (menuKey === "group-info") {
      return (
        <GroupInfoPanel
          chatId={chatId}
          data={bundle}
          actions={actions}
          apiActions={{
            deleteMessage: memberActions.deleteMessage,
            pinMessage: memberActions.pinMessage,
            unpinMessage: memberActions.unpinMessage,
            createInvite: memberActions.createInvite,
            revokeInvite: memberActions.revokeInvite,
            promote: memberActions.promote,
            demote: memberActions.demote,
            setTitle: memberActions.setTitle,
            updateProfile: memberActions.updateProfile,
          }}
        />
      );
    }
    if (menuKey === "group-members") {
      return (
        <GroupManagePanel
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
      return (
        <AiConfigPanel
          config={runtimeConfigQuery.data}
          loading={runtimeConfigQuery.isLoading}
          saving={savingRuntimeConfig}
          questionsLoading={verificationQuestionsQuery.isLoading || verificationQuestionsQuery.isFetching}
          questionsGenerating={generatingVerificationQuestions}
          verificationQuestions={verificationQuestionsQuery.data ?? []}
          chatId={chatId || undefined}
          onSave={saveRuntimeConfig}
          onTestModeration={testModerationAi}
          onTestWelcome={testWelcomeAi}
          onCreateQuestion={createVerificationQuestion}
          onUpdateQuestion={updateVerificationQuestion}
          onDeleteQuestion={deleteVerificationQuestion}
          onGenerateQuestions={generateVerificationQuestions}
        />
      );
    }
    if (menuKey === "policy") return <PolicyConfigPanel data={bundle} actions={actions} />;
    if (menuKey === "points") {
      return (
        <PointsPanel
          data={bundle}
          balance={pointsBalanceQuery.data}
          queriedUserId={queriedPointsUserId}
          setQueriedUserId={setQueriedPointsUserId}
          onRefresh={async () => {
            await Promise.all([pointsConfigQuery.refetch(), pointsLeaderboardQuery.refetch(), pointsLedgerQuery.refetch()]);
          }}
          onQueryBalance={async () => {
            await pointsBalanceQuery.refetch();
          }}
          onSaveConfig={async (payload) => {
            await api.updatePointsConfig(chatId, adminToken, payload);
            toast.success("积分配置已更新");
            await pointsConfigQuery.refetch();
          }}
          onAdjustPoints={async (payload) => {
            await api.adjustPoints(chatId, adminToken, payload);
            toast.success("积分已调整");
            await Promise.all([pointsLeaderboardQuery.refetch(), pointsLedgerQuery.refetch(), pointsBalanceQuery.refetch()]);
          }}
        />
      );
    }
    if (menuKey === "lists") return <ListManagePanel data={bundle} actions={actions} />;
    if (menuKey === "audit") return <AuditCenterPanel data={bundle} />;
    if (menuKey === "enforcement") return <EnforcementPanel data={bundle} actions={actions} />;
    if (menuKey === "appeals") return <AppealsPanel data={bundle} />;
    return (
      <SystemSettingsPanel
        baseUrl={baseUrl}
        chatId={chatId}
        knownChats={bundle.knownChats}
        onReloadChats={reloadChats}
        onSaveConnection={(values) => {
          onBaseUrlChange(values.baseUrl);
          setChatId(values.chatId);
          writeStorage("bot_base_url", values.baseUrl);
          writeStorage("bot_chat_id", values.chatId);
          toast.success("连接配置已保存");
        }}
        runtimeState={runtimeState}
        lastSyncText={lastSyncAt ? formatTime(lastSyncAt.toISOString()) : "-"}
      />
    );
  };

  return (
    <AppLayout
      brandTitle="Telegram 管理后台"
      brandSubtitle="Bot Management Console"
      menuItems={menuItems}
      activeMenuKey={menuKey}
      onMenuChange={(key) => setMenuKey(key as MenuKey)}
      onLogout={onLogout}
      headerLeft={
        <>
          <Badge variant={runtimeState === "active" ? "default" : "secondary"}>
            {runtimeState.toUpperCase()}
          </Badge>
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 dark:bg-cyan-500/15 dark:text-cyan-200 dark:border-cyan-400/20">
            {chatId || "未选择 Chat"}
          </Badge>
          <Badge variant="outline" className="hidden sm:inline-flex bg-slate-50 dark:bg-slate-500/15 dark:border-slate-400/20 dark:text-slate-200">
            前端 v{frontendVersion}
          </Badge>
          <Badge variant="outline" className="hidden sm:inline-flex bg-slate-50 dark:bg-slate-500/15 dark:border-slate-400/20 dark:text-slate-200">
            后端 v{backendVersion}
          </Badge>
          <div className="ml-2 flex items-center gap-2 text-xs text-muted-foreground">
            <div className={cn("h-2 w-2 rounded-full", isRefreshing ? "bg-amber-400 animate-pulse" : "bg-emerald-500")} />
            {isRefreshing ? "同步中..." : `最后同步: ${lastSyncAt ? formatTime(lastSyncAt.toISOString()) : "-"}`}
          </div>
        </>
      }
      headerRight={
        <div className="flex items-center gap-2">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={() => void refreshVisibleData()}>
                  <RefreshCw className={cn("h-4 w-4", isRefreshing && "animate-spin")} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>手动刷新数据</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {chatReady && overviewQuery.data?.capabilities
            ? (() => {
                const report = buildPermissionCheck(overviewQuery.data.capabilities);
                return (
                  <Badge variant={report.allGood ? "outline" : "destructive"} className={cn(report.allGood && "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-200 dark:border-emerald-400/20")}>
                    {report.allGood ? "权限正常" : `缺权限: ${report.missing.length}`}
                  </Badge>
                );
              })()
            : null}
        </div>
      }
    >
      {statusQuery.isError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>状态查询失败</AlertTitle>
          <AlertDescription>{getErrorMessage(statusQuery.error)}</AlertDescription>
        </Alert>
      )}
      <div key={menuKey} className="admin-panel-stage">
        {renderContent()}
      </div>
    </AppLayout>
  );
}
