import { useMemo, useState } from "react";
import { Ban, Check, ChevronsUpDown, RotateCcw, Search, ShieldMinus, ShieldX, UserRoundCog, UserRoundX } from "lucide-react";
import { toast } from "sonner";
import type { AdminActionResult, ChatMemberBrief } from "@/lib/api";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { formatTime, translateChatMemberStatus, translatePermission } from "@/lib/helpers";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { cn } from "@/lib/utils";

type Props = {
  data: AdminDataBundle;
  actions: AdminActions;
  autoRefresh: boolean;
  setAutoRefresh: (value: boolean) => void;
  memberKeyword: string;
  setMemberKeyword: (value: string) => void;
  requestMembersRefresh: () => Promise<void>;
  apiActions: {
    getMember: (userId: string) => Promise<AdminActionResult>;
    mute: (userId: string, duration: number) => Promise<AdminActionResult>;
    unmute: (userId: string) => Promise<AdminActionResult>;
    ban: (userId: string) => Promise<AdminActionResult>;
    kick: (userId: string) => Promise<AdminActionResult>;
    unban: (userId: string) => Promise<AdminActionResult>;
  };
};

const PAGE_SIZE = 8;

function getStatusBadgeClass(status: string | null) {
  const normalized = String(status || "unknown").toLowerCase();
  if (normalized === "restricted") return "bg-amber-500 text-white";
  if (normalized === "kicked" || normalized === "banned") return "bg-rose-600 text-white";
  if (normalized === "member") return "bg-emerald-500 text-white";
  if (normalized === "administrator" || normalized === "creator" || normalized === "owner") return "bg-sky-600 text-white dark:bg-cyan-500 dark:text-slate-950";
  return "";
}

function getMemberProtection(member: ChatMemberBrief | null, whitelistValues: Set<string>, adminIds: Set<number>) {
  if (!member) return { protected: false, reason: "" };
  if (member.is_bot) {
    return { protected: true, reason: "机器人账号受保护，不能执行禁言、封禁或踢出。" };
  }
  const status = String(member.current_status || "").toLowerCase();
  if (adminIds.has(member.user_id) || status === "administrator" || status === "creator" || status === "owner") {
    return { protected: true, reason: "群主和管理员受保护，不能执行禁言、封禁或踢出。" };
  }
  if (member.is_whitelisted || whitelistValues.has(String(member.user_id)) || (member.username && whitelistValues.has(member.username))) {
    return { protected: true, reason: "白名单成员受保护，不能执行禁言、封禁或踢出。" };
  }
  return { protected: false, reason: "" };
}

export function GroupManagePanel({
  data,
  actions,
  autoRefresh,
  setAutoRefresh,
  memberKeyword,
  setMemberKeyword,
  requestMembersRefresh,
  apiActions,
}: Props) {
  const [muteSeconds, setMuteSeconds] = useState("600");
  const [memberDialogOpen, setMemberDialogOpen] = useState(false);
  const [activeMember, setActiveMember] = useState<ChatMemberBrief | null>(null);
  const [refreshingMemberId, setRefreshingMemberId] = useState<string>("");
  const [memberActionMenu, setMemberActionMenu] = useState<"restrict" | "ban" | "status">("restrict");
  const [memberPage, setMemberPage] = useState(1);
  const [searchOpen, setSearchOpen] = useState(false);

  const capabilities = data.overview?.capabilities ?? {};
  const missingCapabilities = Object.entries(capabilities).filter(([, ok]) => !ok).map(([name]) => translatePermission(name));

  const pagedMembers = useMemo(() => {
    const start = (memberPage - 1) * PAGE_SIZE;
    return data.members.slice(start, start + PAGE_SIZE);
  }, [data.members, memberPage]);

  const memberSearchOptions = useMemo(
    () =>
      data.members.slice(0, 200).map((member) => {
        const displayName = `${member.first_name ?? ""} ${member.last_name ?? ""}`.trim() || "未知用户";
        const username = member.username ? `@${member.username}` : "无用户名";
        return {
          value: String(member.user_id),
          displayName,
          username,
          userId: String(member.user_id),
          searchText: `${displayName} ${username} ${member.user_id}`,
        };
      }),
    [data.members],
  );

  const totalPages = Math.max(1, Math.ceil(data.members.length / PAGE_SIZE));
  const whitelistValues = useMemo(() => new Set(data.whitelist.map((item) => item.value)), [data.whitelist]);
  const adminIds = useMemo(() => new Set((data.overview?.administrators ?? []).map((item) => item.user_id)), [data.overview?.administrators]);
  const activeMemberProtection = useMemo(
    () => getMemberProtection(activeMember, whitelistValues, adminIds),
    [activeMember, whitelistValues, adminIds],
  );

  const openMemberDialog = (member: ChatMemberBrief) => {
    setActiveMember(member);
    setMemberActionMenu("restrict");
    setMemberDialogOpen(true);
  };

  const closeMemberDialog = () => {
    setMemberDialogOpen(false);
    setActiveMember(null);
  };

  const refreshSingleMember = async (member: ChatMemberBrief) => {
    const userId = String(member.user_id);
    setRefreshingMemberId(userId);
    try {
      const result = await apiActions.getMember(userId);
      const status = String(result.data?.status ?? member.current_status ?? "unknown");
      toast.success(`用户状态已刷新：${translateChatMemberStatus(status)}`);
      await requestMembersRefresh();
    } catch {
      toast.error("刷新用户状态失败");
    } finally {
      setRefreshingMemberId("");
    }
  };

  const handleMemberAction = async (runner: () => Promise<AdminActionResult>, successText: string) => {
    await actions.runAction(runner, successText);
    await requestMembersRefresh();
    closeMemberDialog();
  };

  return (
    <>
      <Card className="admin-surface-card">
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>成员管理</CardTitle>
            <p className="text-sm text-muted-foreground">仅展示机器人实际收到过消息、或已被处置过的用户；这不是 Telegram 全量成员列表。</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-muted-foreground">5秒自动刷新</span>
            <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} />
            <Button variant="outline" onClick={() => void requestMembersRefresh()}>
              <RotateCcw className="mr-2 h-4 w-4" />
              立即刷新
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {missingCapabilities.length > 0 ? (
            <Alert className="border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-100">
              <AlertTitle>权限不足</AlertTitle>
              <AlertDescription>当前缺少权限：{missingCapabilities.join("、")}。相关动作可能降级或失败。</AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row">
            <Popover open={searchOpen} onOpenChange={setSearchOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={searchOpen}
                  className="max-w-md justify-between font-normal text-muted-foreground"
                >
                  <span className="truncate">
                    {memberKeyword
                      ? (() => {
                          const selected = memberSearchOptions.find((item) => item.userId === memberKeyword);
                          return selected ? `${selected.displayName} ${selected.username} (${selected.userId})` : memberKeyword;
                        })()
                      : "搜索 user_id / 用户名 / 姓名"}
                  </span>
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[360px] p-0" align="start">
                <Command shouldFilter>
                  <CommandInput
                    placeholder="搜索 user_id / 用户名 / 姓名"
                    value={memberKeyword}
                    onValueChange={setMemberKeyword}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        setSearchOpen(false);
                        void requestMembersRefresh();
                      }
                    }}
                  />
                  <CommandList>
                    <CommandEmpty>没有匹配的成员，按 Enter 直接搜索当前输入。</CommandEmpty>
                    <CommandGroup heading="成员候选">
                      {memberSearchOptions.map((item) => (
                        <CommandItem
                          key={`${item.userId}-${item.username}`}
                          value={item.searchText}
                          onSelect={() => {
                            setMemberKeyword(item.userId);
                            setSearchOpen(false);
                            void requestMembersRefresh();
                          }}
                        >
                          <Check className={cn("mr-2 h-4 w-4", memberKeyword === item.userId ? "opacity-100" : "opacity-0")} />
                          <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
                            <span className="truncate">{item.displayName}</span>
                            <span className="shrink-0 rounded-full bg-sky-50 px-2.5 py-0.5 text-xs text-sky-700 dark:bg-cyan-500/15 dark:text-cyan-200">
                              {item.username}
                            </span>
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            <Button variant="outline" onClick={() => void requestMembersRefresh()}>
              <Search className="mr-2 h-4 w-4" />
              搜索
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[160px]">备注名</TableHead>
                <TableHead className="w-[150px]">用户名</TableHead>
                <TableHead className="w-[120px]">User ID</TableHead>
                <TableHead className="w-[180px]">最后活跃</TableHead>
                <TableHead className="w-[160px]">当前状态</TableHead>
                <TableHead className="w-[84px] text-center">违规分</TableHead>
                <TableHead className="w-[200px]">快捷操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagedMembers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                    {data.isLoading ? "成员列表加载中..." : "暂无成员数据"}
                  </TableCell>
                </TableRow>
              ) : (
                pagedMembers.map((row) => {
                  const displayName = `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim() || "-";
                  const protection = getMemberProtection(row, whitelistValues, adminIds);
                  return (
                    <TableRow key={row.user_id}>
                      <TableCell className="max-w-[160px] truncate font-medium">{displayName}</TableCell>
                      <TableCell className="max-w-[150px] truncate text-muted-foreground">
                        {row.username ? `@${row.username}` : "无用户名"}
                      </TableCell>
                      <TableCell>{row.user_id}</TableCell>
                      <TableCell className="w-[180px] text-muted-foreground">{formatTime(row.last_message_at)}</TableCell>
                      <TableCell className="w-[160px]">
                        <div className="flex flex-col gap-1">
                          <div className="w-fit">
                            <Badge className={getStatusBadgeClass(row.current_status)}>{translateChatMemberStatus(row.current_status)}</Badge>
                          </div>
                          {row.current_status_until_date ? (
                            <span className="text-xs text-muted-foreground">至 {formatTime(row.current_status_until_date)}</span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant={row.strike_score > 0 ? "outline" : "secondary"} className={row.strike_score > 0 ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200" : ""}>
                          {row.strike_score}
                        </Badge>
                      </TableCell>
                      <TableCell className="w-[200px]">
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            className="h-8 min-w-[76px] bg-sky-600 px-4 text-white hover:bg-sky-500 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
                            onClick={() => openMemberDialog(row)}
                          >
                            <UserRoundCog className="mr-2 h-4 w-4" />
                            操作
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 min-w-[76px] border-emerald-200 bg-emerald-50 px-4 text-emerald-700 hover:bg-emerald-100 hover:text-emerald-800 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-200 dark:hover:bg-emerald-500/20 dark:hover:text-emerald-100"
                            disabled={refreshingMemberId === String(row.user_id)}
                            onClick={() => void refreshSingleMember(row)}
                          >
                            <RotateCcw className="mr-2 h-4 w-4" />
                            {refreshingMemberId === String(row.user_id) ? "刷新中..." : "刷新"}
                          </Button>
                        </div>
                        {protection.protected ? (
                          <p className="mt-1 text-xs text-amber-600 dark:text-amber-300">{protection.reason}</p>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm text-muted-foreground">
              第 {memberPage} / {totalPages} 页，共 {data.members.length} 条
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={memberPage <= 1} onClick={() => setMemberPage((prev) => prev - 1)}>
                上一页
              </Button>
              <Button variant="outline" size="sm" disabled={memberPage >= totalPages} onClick={() => setMemberPage((prev) => prev + 1)}>
                下一页
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={memberDialogOpen} onOpenChange={(open) => !open && closeMemberDialog()}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {activeMember ? `用户操作：${activeMember.first_name ?? activeMember.username ?? activeMember.user_id}` : "用户操作"}
            </DialogTitle>
            <DialogDescription>针对单个成员执行禁言、封禁和状态查询。</DialogDescription>
          </DialogHeader>

          {activeMember ? (
            <div className="rounded-xl border bg-muted/20 p-4">
              <div className="flex flex-col gap-1">
                <span className="font-medium">{`${activeMember.first_name ?? ""} ${activeMember.last_name ?? ""}`.trim() || activeMember.username || "-"}</span>
                <span className="text-sm text-muted-foreground">User ID: {activeMember.user_id}</span>
                <span className="text-sm text-muted-foreground">当前状态：{translateChatMemberStatus(activeMember.current_status)}</span>
                {activeMemberProtection.protected ? (
                  <span className="text-sm text-amber-600 dark:text-amber-300">{activeMemberProtection.reason}</span>
                ) : null}
              </div>
            </div>
          ) : null}

          <Tabs value={memberActionMenu} onValueChange={(value) => setMemberActionMenu(value as "restrict" | "ban" | "status")}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="restrict">禁言管理</TabsTrigger>
              <TabsTrigger value="ban">封禁管理</TabsTrigger>
              <TabsTrigger value="status">状态信息</TabsTrigger>
            </TabsList>

            <TabsContent value="restrict" className="space-y-4">
              <div className="space-y-2">
                <Label>禁言时长（秒）</Label>
                <Input type="number" value={muteSeconds} onChange={(e) => setMuteSeconds(e.target.value)} />
              </div>
              <div className="flex flex-wrap gap-3">
              <Button onClick={() => void handleMemberAction(() => apiActions.mute(String(activeMember?.user_id ?? ""), Number(muteSeconds)), "禁言成功")} disabled={!activeMember || activeMemberProtection.protected}>
                <Ban className="mr-2 h-4 w-4" />
                禁言
              </Button>
              <Button variant="outline" onClick={() => void handleMemberAction(() => apiActions.unmute(String(activeMember?.user_id ?? "")), "解除禁言成功")} disabled={!activeMember}>
                <RotateCcw className="mr-2 h-4 w-4" />
                解禁言
              </Button>
              </div>
            </TabsContent>

            <TabsContent value="ban" className="space-y-4">
              <p className="text-sm text-muted-foreground">这里是高风险动作，请确认后再执行。</p>
              <div className="flex flex-wrap gap-3">
              <Button variant="destructive" onClick={() => void handleMemberAction(() => apiActions.ban(String(activeMember?.user_id ?? "")), "封禁成功")} disabled={!activeMember || activeMemberProtection.protected}>
                <ShieldX className="mr-2 h-4 w-4" />
                封禁
              </Button>
              <Button variant="destructive" onClick={() => void handleMemberAction(() => apiActions.kick(String(activeMember?.user_id ?? "")), "踢出群成功")} disabled={!activeMember || activeMemberProtection.protected}>
                <UserRoundX className="mr-2 h-4 w-4" />
                踢出群
              </Button>
              <Button variant="outline" onClick={() => void handleMemberAction(() => apiActions.unban(String(activeMember?.user_id ?? "")), "解封成功")} disabled={!activeMember}>
                <ShieldMinus className="mr-2 h-4 w-4" />
                解封
              </Button>
              </div>
            </TabsContent>

            <TabsContent value="status" className="space-y-2 text-sm">
              <p>当前状态：{translateChatMemberStatus(activeMember?.current_status)}</p>
              <p className="text-muted-foreground">状态截止：{activeMember?.current_status_until_date ? formatTime(activeMember.current_status_until_date) : "无"}</p>
              <p className="text-muted-foreground">最后活跃：{formatTime(activeMember?.last_message_at)}</p>
              <p className="text-muted-foreground">违规分：{activeMember?.strike_score ?? 0}</p>
            </TabsContent>
          </Tabs>

          <DialogFooter>
            <Button variant="outline" onClick={closeMemberDialog}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
