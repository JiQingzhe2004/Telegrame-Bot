import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Shield, Sparkles, Undo2 } from "lucide-react";
import { ApiClient, type AppealRecord, type AuditRecord, type ChatSettings, type EnforcementRecord, type KnownChat, type ListItem } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function levelBadge(level: number) {
  if (level >= 3) return <Badge variant="destructive">L3 极严重</Badge>;
  if (level === 2) return <Badge variant="secondary">L2 严重</Badge>;
  if (level === 1) return <Badge variant="outline">L1 轻微</Badge>;
  return <Badge variant="outline">L0 正常</Badge>;
}

function formatTime(text: string) {
  return new Date(text).toLocaleString();
}

type RuntimeMode = "setup" | "active" | "loading";

export function App() {
  const [baseUrl, setBaseUrl] = useState(localStorage.getItem("bot_base_url") || window.location.origin || "http://127.0.0.1:10010");
  const [mode, setMode] = useState<RuntimeMode>("loading");
  const [globalMessage, setGlobalMessage] = useState("");
  const client = useMemo(() => new ApiClient(baseUrl), [baseUrl]);

  useEffect(() => {
    localStorage.setItem("bot_base_url", baseUrl);
  }, [baseUrl]);

  useEffect(() => {
    (async () => {
      try {
        const state = await client.getRuntimeState();
        setMode(state.state);
      } catch {
        setMode("setup");
        setGlobalMessage("无法读取运行状态，请确认后端服务已启动。");
      }
    })();
  }, [client]);

  if (mode === "loading") {
    return (
      <main className="mx-auto min-h-screen w-full max-w-3xl px-4 py-10">
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle>正在连接服务...</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-4/5" />
          </CardContent>
        </Card>
      </main>
    );
  }

  if (mode === "setup") {
    return (
      <SetupWizard
        baseUrl={baseUrl}
        setBaseUrl={setBaseUrl}
        message={globalMessage}
        setMessage={setGlobalMessage}
        onActivated={() => setMode("active")}
      />
    );
  }

  return <AdminConsole baseUrl={baseUrl} setBaseUrl={setBaseUrl} onNeedSetup={() => setMode("setup")} />;
}

function SetupWizard({
  baseUrl,
  setBaseUrl,
  message,
  setMessage,
  onActivated,
}: {
  baseUrl: string;
  setBaseUrl: (value: string) => void;
  message: string;
  setMessage: (value: string) => void;
  onActivated: () => void;
}) {
  const client = useMemo(() => new ApiClient(baseUrl), [baseUrl]);
  const [code, setCode] = useState("");
  const [setupToken, setSetupToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [activating, setActivating] = useState(false);

  const [form, setForm] = useState({
    bot_token: "",
    openai_api_key: "",
    openai_base_url: "",
    admin_api_token: "",
    run_mode: "polling",
    webhook_public_url: "",
    ai_low_risk_model: "gpt-4.1-mini",
    ai_high_risk_model: "gpt-5.2",
  });

  const doAuth = async () => {
    setSubmitting(true);
    try {
      const out = await client.setupAuth(code.trim());
      setSetupToken(out.setup_token);
      setMessage("口令验证成功，继续填写配置。");
    } catch (err) {
      setMessage(`口令验证失败：${String(err)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const reissueCode = async () => {
    setSubmitting(true);
    try {
      const out = await client.setupReissueCode();
      setCode(out.code);
      setMessage(`已生成新口令（${out.expires_in_minutes} 分钟有效）。`);
    } catch (err) {
      setMessage(`重发口令失败：${String(err)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const saveAndActivate = async () => {
    if (!setupToken) {
      setMessage("请先完成口令验证。");
      return;
    }
    setSubmitting(true);
    setActivating(true);
    try {
      await client.setupConfig(setupToken, form);
      await client.setupActivate(setupToken);
      localStorage.setItem("bot_admin_token", form.admin_api_token);
      setMessage("配置完成，服务已激活。");
      onActivated();
    } catch (err) {
      setMessage(`配置失败：${String(err)}`);
    } finally {
      setActivating(false);
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-4 py-10 md:px-8">
      <Card className="glass-panel mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-2xl">
            <Sparkles className="h-6 w-6" />
            首次配置向导
          </CardTitle>
          <CardDescription>终端只负责安装与启动，业务配置全部在这里完成。</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label>后端地址</Label>
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </div>
            <div className="flex flex-col gap-2">
              <Label>首次启动口令</Label>
              <div className="flex gap-2">
                <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="终端里打印的口令" />
                <Button onClick={() => void doAuth()} disabled={submitting}>
                  验证
                </Button>
                <Button variant="outline" onClick={() => void reissueCode()} disabled={submitting}>
                  重发
                </Button>
              </div>
            </div>
        </CardContent>
      </Card>

      <Card className="glass-panel">
        <CardHeader>
          <CardTitle>运行配置</CardTitle>
          <CardDescription>填写后点“保存并激活”，无需重启进程。</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label>BOT Token</Label>
            <Input value={form.bot_token} onChange={(e) => setForm({ ...form, bot_token: e.target.value })} />
          </div>
          <div className="flex flex-col gap-2">
            <Label>管理 API Token</Label>
            <Input value={form.admin_api_token} onChange={(e) => setForm({ ...form, admin_api_token: e.target.value })} />
          </div>
          <div className="flex flex-col gap-2">
            <Label>OpenAI/兼容平台 Key</Label>
            <Input value={form.openai_api_key} onChange={(e) => setForm({ ...form, openai_api_key: e.target.value })} />
          </div>
          <div className="flex flex-col gap-2">
            <Label>兼容平台 Base URL（可空）</Label>
            <Input value={form.openai_base_url} onChange={(e) => setForm({ ...form, openai_base_url: e.target.value })} />
          </div>
          <div className="flex flex-col gap-2">
            <Label>运行模式</Label>
            <Select value={form.run_mode} onValueChange={(v) => setForm({ ...form, run_mode: v })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="polling">polling</SelectItem>
                  <SelectItem value="webhook">webhook</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-2">
            <Label>Webhook 公网地址（webhook 模式必填）</Label>
            <Input value={form.webhook_public_url} onChange={(e) => setForm({ ...form, webhook_public_url: e.target.value })} />
          </div>
          <div className="flex flex-col gap-2">
            <Label>低风险模型</Label>
            <Input value={form.ai_low_risk_model} onChange={(e) => setForm({ ...form, ai_low_risk_model: e.target.value })} />
          </div>
          <div className="flex flex-col gap-2">
            <Label>高风险模型</Label>
            <Input value={form.ai_high_risk_model} onChange={(e) => setForm({ ...form, ai_high_risk_model: e.target.value })} />
          </div>
          <div className="md:col-span-2 flex flex-col gap-2">
            <Button className="w-full" onClick={() => void saveAndActivate()} disabled={submitting}>
              {activating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  正在保存并激活...
                </>
              ) : (
                "保存并激活"
              )}
            </Button>
            {activating && <p className="text-xs text-muted-foreground">正在连接 Telegram 并应用配置，通常需要 1-5 秒。</p>}
          </div>
        </CardContent>
      </Card>

      {message && (
        <div className="mt-4 flex items-start gap-2 rounded-md border bg-white p-3">
          <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
          <span>{message}</span>
        </div>
      )}
    </main>
  );
}

function AdminConsole({
  baseUrl,
  setBaseUrl,
  onNeedSetup,
}: {
  baseUrl: string;
  setBaseUrl: (value: string) => void;
  onNeedSetup: () => void;
}) {
  const [adminToken, setAdminToken] = useState(localStorage.getItem("bot_admin_token") || "");
  const [chatId, setChatId] = useState("");
  const deferredChatId = useDeferredValue(chatId.trim());
  const client = useMemo(() => new ApiClient(baseUrl), [baseUrl]);

  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [settings, setSettings] = useState<ChatSettings | null>(null);
  const [knownChats, setKnownChats] = useState<KnownChat[]>([]);
  const [whitelist, setWhitelist] = useState<ListItem[]>([]);
  const [blacklist, setBlacklist] = useState<ListItem[]>([]);
  const [audits, setAudits] = useState<AuditRecord[]>([]);
  const [enforcements, setEnforcements] = useState<EnforcementRecord[]>([]);
  const [appeals, setAppeals] = useState<AppealRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [newWhitelist, setNewWhitelist] = useState("");
  const [newBlacklist, setNewBlacklist] = useState("");
  const [rollbackId, setRollbackId] = useState<number | null>(null);

  useEffect(() => {
    localStorage.setItem("bot_admin_token", adminToken);
  }, [adminToken]);

  const canLoad = Boolean(baseUrl && adminToken && deferredChatId);

  const loadAll = async () => {
    if (!canLoad) {
      setMessage("请先填写地址、管理令牌和 Chat ID。");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const [runtime, s, chats, cfg, wl, bl, ad, en, ap] = await Promise.all([
        client.getRuntimeState(),
        client.getStatus(adminToken),
        client.listChats(adminToken),
        client.getSettings(deferredChatId, adminToken),
        client.listWhitelist(deferredChatId, adminToken),
        client.listBlacklist(deferredChatId, adminToken),
        client.listAudits(deferredChatId, adminToken, 100),
        client.listEnforcements(deferredChatId, adminToken, 100),
        client.listAppeals(deferredChatId, adminToken),
      ]);
      if (runtime.state === "setup") {
        onNeedSetup();
        return;
      }
      startTransition(() => {
        setStatus(s);
        setKnownChats(chats);
        setSettings(cfg);
        setWhitelist(wl);
        setBlacklist(bl);
        setAudits(ad);
        setEnforcements(en);
        setAppeals(ap);
      });
      setMessage("数据刷新完成。");
    } catch (err) {
      setMessage(`加载失败：${String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  const loadKnownChats = async () => {
    if (!baseUrl || !adminToken) {
      setMessage("请先填写 API 地址和管理令牌。");
      return;
    }
    try {
      const chats = await client.listChats(adminToken);
      setKnownChats(chats);
      if (!chatId && chats.length > 0) {
        setChatId(String(chats[0].chat_id));
      }
      if (!chats.length) {
        setMessage("暂无群记录。请在群里 @机器人 发一条消息后再点自动获取。");
      } else {
        setMessage(`已获取 ${chats.length} 个群。`);
      }
    } catch (err) {
      setMessage(`获取群列表失败：${String(err)}`);
    }
  };

  useEffect(() => {
    if (!canLoad) return;
    void loadAll();
  }, [baseUrl, adminToken, deferredChatId, canLoad]);

  const updateSetting = async (payload: Partial<ChatSettings>) => {
    if (!settings) return;
    try {
      const next = await client.updateSettings(deferredChatId, adminToken, payload);
      setSettings(next);
      setMessage("配置已更新。");
    } catch (err) {
      setMessage(`更新失败：${String(err)}`);
    }
  };

  const addToList = async (type: "white" | "black") => {
    const value = type === "white" ? newWhitelist.trim() : newBlacklist.trim();
    if (!value) return;
    try {
      if (type === "white") {
        await client.addWhitelist(deferredChatId, adminToken, value);
        setNewWhitelist("");
      } else {
        await client.addBlacklist(deferredChatId, adminToken, value);
        setNewBlacklist("");
      }
      await loadAll();
    } catch (err) {
      setMessage(`新增失败：${String(err)}`);
    }
  };

  const removeFromList = async (type: "white" | "black", value: string) => {
    try {
      if (type === "white") await client.deleteWhitelist(deferredChatId, adminToken, value);
      else await client.deleteBlacklist(deferredChatId, adminToken, value);
      await loadAll();
    } catch (err) {
      setMessage(`删除失败：${String(err)}`);
    }
  };

  const rollback = async () => {
    if (!rollbackId) return;
    try {
      await client.rollback(adminToken, rollbackId);
      setMessage(`回滚请求已提交：#${rollbackId}`);
      setRollbackId(null);
      await loadAll();
    } catch (err) {
      setMessage(`回滚失败：${String(err)}`);
    }
  };

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-4 py-8 md:px-8">
      <section className="mb-6 flex flex-col gap-4 rounded-2xl border border-white/70 glass-panel p-6 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold tracking-tight">管理机器人控制台</h1>
          <p className="text-sm text-muted-foreground">运行中，支持热更新策略与审计操作。</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            <Shield className="mr-1 h-3.5 w-3.5" />
            ACTIVE
          </Badge>
          <Button variant="outline" onClick={() => void loadAll()} disabled={loading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新
          </Button>
        </div>
      </section>

      <section className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card className="glass-panel lg:col-span-2">
          <CardHeader>
            <CardTitle>连接参数</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            <div className="flex flex-col gap-2">
              <Label>API 地址</Label>
              <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label>管理令牌</Label>
              <Input value={adminToken} onChange={(e) => setAdminToken(e.target.value)} type="password" />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Chat ID</Label>
              <Input value={chatId} onChange={(e) => setChatId(e.target.value)} />
            </div>
            <div className="md:col-span-3 flex items-end gap-2">
              <div className="flex-1 flex flex-col gap-2">
                <Label>自动获取到的群</Label>
                <Select value={chatId} onValueChange={(v) => setChatId(v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择群后自动填充 Chat ID" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {knownChats.map((c) => (
                        <SelectItem key={c.chat_id} value={String(c.chat_id)}>
                          {(c.title && c.title.trim()) || `chat:${c.chat_id}`} ({c.chat_id})
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
              <Button variant="outline" onClick={() => void loadKnownChats()}>
                自动获取
              </Button>
            </div>
          </CardContent>
        </Card>
        <Card className="glass-panel">
          <CardHeader>
            <CardTitle>系统状态</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            {!status && <span className="text-muted-foreground">点击刷新加载</span>}
            {status &&
              Object.entries(status).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <span className="text-muted-foreground">{k}</span>
                  <span className="font-mono text-xs">{String(v)}</span>
                </div>
              ))}
            {message && (
              <div className="mt-2 flex items-start gap-2 rounded-md border bg-white px-3 py-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
                <span>{message}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <Tabs defaultValue="settings">
        <TabsList>
          <TabsTrigger value="settings">群配置</TabsTrigger>
          <TabsTrigger value="lists">白黑名单</TabsTrigger>
          <TabsTrigger value="audit">审计记录</TabsTrigger>
          <TabsTrigger value="enforcement">处置记录</TabsTrigger>
          <TabsTrigger value="appeals">申诉</TabsTrigger>
        </TabsList>

        <TabsContent value="settings">
          <Card className="glass-panel">
            <CardHeader>
              <CardTitle>策略设置</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-6 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label>模式</Label>
                <Select value={settings?.mode ?? "balanced"} onValueChange={(v) => void updateSetting({ mode: v as ChatSettings["mode"] })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="strict">strict</SelectItem>
                      <SelectItem value="balanced">balanced</SelectItem>
                      <SelectItem value="relaxed">relaxed</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex h-10 items-center justify-between rounded-md border bg-white px-3">
                <div className="flex items-center gap-2">
                  <Label htmlFor="ai-enabled" className="mb-0">
                    AI 开关
                  </Label>
                  <span className="text-xs text-muted-foreground">语义判定</span>
                </div>
                <Switch id="ai-enabled" checked={settings?.ai_enabled ?? false} onCheckedChange={(v) => void updateSetting({ ai_enabled: v })} />
              </div>
              <div className="flex flex-col gap-2">
                <Label>AI 阈值 (0~1)</Label>
                <Input
                  type="number"
                  step={0.01}
                  min={0}
                  max={1}
                  value={settings?.ai_threshold ?? 0.75}
                  onChange={(e) => void updateSetting({ ai_threshold: Number(e.target.value) })}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label>L3 禁言秒数</Label>
                <Input
                  type="number"
                  value={settings?.level3_mute_seconds ?? 604800}
                  onChange={(e) => void updateSetting({ level3_mute_seconds: Number(e.target.value) })}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lists">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="glass-panel">
              <CardHeader>
                <CardTitle>白名单</CardTitle>
                <CardDescription>支持 @username 或 user_id</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="flex gap-2">
                  <Input value={newWhitelist} onChange={(e) => setNewWhitelist(e.target.value)} />
                  <Button onClick={() => void addToList("white")}>添加</Button>
                </div>
                <Separator />
                {whitelist.map((item) => (
                  <div key={item.id} className="flex items-center justify-between rounded-md border bg-white px-3 py-2">
                    <span className="font-mono text-xs">{item.value}</span>
                    <Button size="sm" variant="outline" onClick={() => void removeFromList("white", item.value)}>
                      删除
                    </Button>
                  </div>
                ))}
              </CardContent>
            </Card>
            <Card className="glass-panel">
              <CardHeader>
                <CardTitle>黑名单词</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="flex gap-2">
                  <Input value={newBlacklist} onChange={(e) => setNewBlacklist(e.target.value)} />
                  <Button onClick={() => void addToList("black")}>添加</Button>
                </div>
                <Separator />
                {blacklist.map((item) => (
                  <div key={item.id} className="flex items-center justify-between rounded-md border bg-white px-3 py-2">
                    <span className="font-mono text-xs">{item.value}</span>
                    <Button size="sm" variant="outline" onClick={() => void removeFromList("black", item.value)}>
                      删除
                    </Button>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="audit">
          <Card className="glass-panel">
            <CardHeader>
              <CardTitle>审计记录</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>用户</TableHead>
                    <TableHead>级别</TableHead>
                    <TableHead>规则/AI</TableHead>
                    <TableHead>置信度</TableHead>
                    <TableHead>时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {audits.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-mono text-xs">#{item.id}</TableCell>
                      <TableCell className="font-mono text-xs">{item.user_id}</TableCell>
                      <TableCell>{levelBadge(item.final_level)}</TableCell>
                      <TableCell className="max-w-[280px] truncate">{item.rule_hit}</TableCell>
                      <TableCell>{item.confidence.toFixed(2)}</TableCell>
                      <TableCell>{formatTime(item.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="enforcement">
          <Card className="glass-panel">
            <CardHeader>
              <CardTitle>处置记录</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>用户</TableHead>
                    <TableHead>动作</TableHead>
                    <TableHead>原因</TableHead>
                    <TableHead>时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {enforcements.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-mono text-xs">#{item.id}</TableCell>
                      <TableCell className="font-mono text-xs">{item.user_id}</TableCell>
                      <TableCell>
                        <Badge variant={item.action === "mute" || item.action === "ban" ? "destructive" : "secondary"}>{item.action}</Badge>
                      </TableCell>
                      <TableCell className="max-w-[240px] truncate">{item.reason}</TableCell>
                      <TableCell>{formatTime(item.created_at)}</TableCell>
                      <TableCell>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button size="sm" variant="outline" onClick={() => setRollbackId(item.id)} disabled={!["mute", "restrict"].includes(item.action)}>
                              <Undo2 className="mr-1 h-4 w-4" />
                              回滚
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>确认回滚</DialogTitle>
                              <DialogDescription>仅支持回滚 mute/restrict。</DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                              <Button variant="outline" onClick={() => setRollbackId(null)}>
                                取消
                              </Button>
                              <Button onClick={() => void rollback()}>确认回滚</Button>
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appeals">
          <Card className="glass-panel">
            <CardHeader>
              <CardTitle>申诉记录</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {appeals.map((item) => (
                <article key={item.id} className="rounded-lg border bg-white p-4">
                  <header className="mb-2 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">#{item.id}</Badge>
                      <span className="font-mono text-xs">user:{item.user_id}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">{formatTime(item.created_at)}</span>
                  </header>
                  <p className="text-sm">{item.message}</p>
                </article>
              ))}
              {!appeals.length && (
                <div className="flex items-center gap-2 rounded-md border bg-white p-4 text-muted-foreground">
                  <AlertTriangle className="h-4 w-4" />
                  暂无申诉记录
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </main>
  );
}
