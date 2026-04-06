import { useEffect, useState } from "react";
import { Bot, Save, Sparkles } from "lucide-react";
import type { ModerationAiTestResult, RuntimeConfigPublic, VerificationQuestion, WelcomeAiTestResult } from "@/lib/api";
import { VerificationQuestionPanel } from "@/components/admin/VerificationQuestionPanel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

type Props = {
  config?: RuntimeConfigPublic;
  loading: boolean;
  saving: boolean;
  questionsLoading: boolean;
  questionsGenerating: boolean;
  verificationQuestions: VerificationQuestion[];
  chatId?: string;
  onSave: (payload: {
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
    redis_url?: string;
    redis_namespace?: string;
  }) => Promise<void>;
  onTestModeration: (text: string) => Promise<ModerationAiTestResult>;
  onTestWelcome: (userDisplayName: string) => Promise<WelcomeAiTestResult>;
  onCreateQuestion: (payload: { scope: "chat" | "global"; question: string; options: string[]; answer_index: number }) => Promise<void>;
  onUpdateQuestion: (questionId: number, payload: { scope: "chat" | "global"; question: string; options: string[]; answer_index: number }) => Promise<void>;
  onDeleteQuestion: (questionId: number) => Promise<void>;
  onGenerateQuestions: (payload: { scope: "chat" | "global"; count: number; topic_hint?: string }) => Promise<void>;
};

type RuntimeFormState = {
  openai_api_key: string;
  openai_base_url: string;
  ai_low_risk_model: string;
  ai_high_risk_model: string;
  ai_timeout_seconds: string;
  join_verification_enabled: boolean;
  join_verification_timeout_seconds: string;
  join_verification_question_type: "button" | "quiz";
  join_verification_max_attempts: string;
  join_verification_whitelist_bypass: boolean;
  join_welcome_enabled: boolean;
  join_welcome_use_ai: boolean;
  join_welcome_template: string;
  run_mode: "polling" | "webhook";
  webhook_public_url: string;
  webhook_path: string;
  redis_url: string;
  redis_namespace: string;
};

function buildInitialState(config?: RuntimeConfigPublic): RuntimeFormState {
  return {
    openai_api_key: "",
    openai_base_url: config?.openai_base_url || "",
    ai_low_risk_model: config?.ai_low_risk_model || "",
    ai_high_risk_model: config?.ai_high_risk_model || "",
    ai_timeout_seconds: String(config?.ai_timeout_seconds ?? 30),
    join_verification_enabled: config?.join_verification_enabled ?? true,
    join_verification_timeout_seconds: String(config?.join_verification_timeout_seconds ?? 300),
    join_verification_question_type: config?.join_verification_question_type ?? "button",
    join_verification_max_attempts: String(config?.join_verification_max_attempts ?? 3),
    join_verification_whitelist_bypass: config?.join_verification_whitelist_bypass ?? false,
    join_welcome_enabled: config?.join_welcome_enabled ?? true,
    join_welcome_use_ai: config?.join_welcome_use_ai ?? false,
    join_welcome_template: config?.join_welcome_template || "欢迎 {user} 加入 {chat}，请先阅读群规并友善交流。",
    run_mode: config?.run_mode ?? "polling",
    webhook_public_url: config?.webhook_public_url || "",
    webhook_path: config?.webhook_path || "/telegram/webhook",
    redis_url: config?.redis_url || "",
    redis_namespace: config?.redis_namespace || "tmbot",
  };
}

function ResultTable({ rows }: { rows: Array<[string, string]> }) {
  return (
    <div className="rounded-xl border bg-background/80">
      <Table>
        <TableBody>
          {rows.map(([key, value]) => (
            <TableRow key={key}>
              <TableCell className="w-[180px] font-medium">{key}</TableCell>
              <TableCell>{value}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function AiConfigPanel({
  config,
  loading,
  saving,
  questionsLoading,
  questionsGenerating,
  verificationQuestions,
  chatId,
  onSave,
  onTestModeration,
  onTestWelcome,
  onCreateQuestion,
  onUpdateQuestion,
  onDeleteQuestion,
  onGenerateQuestions,
}: Props) {
  const [formState, setFormState] = useState<RuntimeFormState>(buildInitialState(config));
  const [moderationText, setModerationText] = useState("这是一条 AI 审计测试消息。");
  const [welcomeUserDisplayName, setWelcomeUserDisplayName] = useState("测试用户");
  const [testingModeration, setTestingModeration] = useState(false);
  const [testingWelcome, setTestingWelcome] = useState(false);
  const [moderationResult, setModerationResult] = useState<ModerationAiTestResult | null>(null);
  const [welcomeResult, setWelcomeResult] = useState<WelcomeAiTestResult | null>(null);
  const [moderationError, setModerationError] = useState("");
  const [welcomeError, setWelcomeError] = useState("");

  useEffect(() => {
    setFormState(buildInitialState(config));
  }, [config]);

  const canTest = Boolean(chatId);

  const handleModerationTest = async () => {
    if (!moderationText.trim()) return;
    setTestingModeration(true);
    setModerationError("");
    try {
      const result = await onTestModeration(moderationText.trim());
      setModerationResult(result);
    } catch (error) {
      setModerationResult(null);
      setModerationError(error instanceof Error ? error.message : "AI 审计测试失败");
    } finally {
      setTestingModeration(false);
    }
  };

  const handleWelcomeTest = async () => {
    if (!welcomeUserDisplayName.trim()) return;
    setTestingWelcome(true);
    setWelcomeError("");
    try {
      const result = await onTestWelcome(welcomeUserDisplayName.trim());
      setWelcomeResult(result);
    } catch (error) {
      setWelcomeResult(null);
      setWelcomeError(error instanceof Error ? error.message : "欢迎语测试失败");
    } finally {
      setTestingWelcome(false);
    }
  };

  return (
    <Card className="admin-surface-card">
      <CardHeader>
        <CardTitle>AI 与入群配置</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <Alert>
          <AlertTitle>热生效说明</AlertTitle>
          <AlertDescription>这里保存后会自动热生效，无需重启进程。Key 为空时表示不改动已有值。</AlertDescription>
        </Alert>

        {!canTest ? (
          <Alert className="border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-100">
            <AlertTitle>测试受限</AlertTitle>
            <AlertDescription>未选择 Chat，暂时无法发起真实 AI 测试。</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Badge variant="outline">当前运行模式: {config?.run_mode ?? "-"}</Badge>
          <Badge variant="outline">当前 Base URL: {config?.openai_base_url || "官方默认"}</Badge>
          <Badge variant="outline">状态存储: {config?.has_redis_url ? "已配置 Redis" : "未配置 Redis"}</Badge>
          <Badge variant="outline">Redis Namespace: {config?.redis_namespace || "tmbot"}</Badge>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <Label>OpenAI/兼容平台 API Key（留空不修改）</Label>
            <Input type="password" placeholder="sk-..." value={formState.openai_api_key} onChange={(e) => setFormState((prev) => ({ ...prev, openai_api_key: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>Base URL（可空）</Label>
            <Input placeholder="https://api.openai.com/v1" value={formState.openai_base_url} onChange={(e) => setFormState((prev) => ({ ...prev, openai_base_url: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>低风险模型</Label>
            <Input value={formState.ai_low_risk_model} onChange={(e) => setFormState((prev) => ({ ...prev, ai_low_risk_model: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>高风险模型</Label>
            <Input value={formState.ai_high_risk_model} onChange={(e) => setFormState((prev) => ({ ...prev, ai_high_risk_model: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>AI 超时（秒）</Label>
            <Input type="number" min="1" max="120" value={formState.ai_timeout_seconds} onChange={(e) => setFormState((prev) => ({ ...prev, ai_timeout_seconds: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>验证方式</Label>
            <Select value={formState.join_verification_question_type} onValueChange={(value) => setFormState((prev) => ({ ...prev, join_verification_question_type: value as "button" | "quiz" }))}>
              <SelectTrigger>
                <SelectValue placeholder="请选择验证方式" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="button">按钮验证</SelectItem>
                  <SelectItem value="quiz">题库问答</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>入群验证超时（秒）</Label>
            <Input type="number" min="30" max="3600" value={formState.join_verification_timeout_seconds} onChange={(e) => setFormState((prev) => ({ ...prev, join_verification_timeout_seconds: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>最大尝试次数</Label>
            <Input type="number" min="1" max="10" value={formState.join_verification_max_attempts} onChange={(e) => setFormState((prev) => ({ ...prev, join_verification_max_attempts: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>运行模式</Label>
            <Select value={formState.run_mode} onValueChange={(value) => setFormState((prev) => ({ ...prev, run_mode: value as "polling" | "webhook" }))}>
              <SelectTrigger>
                <SelectValue placeholder="请选择运行模式" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="polling">Polling</SelectItem>
                  <SelectItem value="webhook">Webhook</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Webhook 公网地址</Label>
            <Input placeholder="https://example.com" value={formState.webhook_public_url} onChange={(e) => setFormState((prev) => ({ ...prev, webhook_public_url: e.target.value }))} />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label>Webhook Path</Label>
            <Input placeholder="/telegram/webhook" value={formState.webhook_path} onChange={(e) => setFormState((prev) => ({ ...prev, webhook_path: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>Redis URL（留空不修改）</Label>
            <Input placeholder="redis://redis:6379/0" value={formState.redis_url} onChange={(e) => setFormState((prev) => ({ ...prev, redis_url: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>Redis Namespace</Label>
            <Input value={formState.redis_namespace} onChange={(e) => setFormState((prev) => ({ ...prev, redis_namespace: e.target.value }))} />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label>欢迎语模板（支持 {"{user} / {chat}"}）</Label>
            <Textarea rows={3} value={formState.join_welcome_template} onChange={(e) => setFormState((prev) => ({ ...prev, join_welcome_template: e.target.value }))} />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-1">
                <Label className="text-sm font-semibold">入群验证开关</Label>
                <p className="text-xs text-muted-foreground">控制新成员是否需要通过验证。</p>
              </div>
              <Switch checked={formState.join_verification_enabled} onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, join_verification_enabled: checked }))} />
            </div>
          </div>
          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-1">
                <Label className="text-sm font-semibold">白名单跳过验证</Label>
                <p className="text-xs text-muted-foreground">白名单成员入群时直接放行。</p>
              </div>
              <Switch checked={formState.join_verification_whitelist_bypass} onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, join_verification_whitelist_bypass: checked }))} />
            </div>
          </div>
          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-1">
                <Label className="text-sm font-semibold">欢迎语开关</Label>
                <p className="text-xs text-muted-foreground">成员通过验证后自动发送欢迎消息。</p>
              </div>
              <Switch checked={formState.join_welcome_enabled} onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, join_welcome_enabled: checked }))} />
            </div>
          </div>
          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-1">
                <Label className="text-sm font-semibold">欢迎语使用 AI</Label>
                <p className="text-xs text-muted-foreground">根据成员信息和群信息动态生成欢迎语。</p>
              </div>
              <Switch checked={formState.join_welcome_use_ai} onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, join_welcome_use_ai: checked }))} />
            </div>
          </div>
        </div>

        <div>
          <Button
            disabled={saving || loading}
            onClick={() =>
              void onSave({
                openai_api_key: formState.openai_api_key.trim() || undefined,
                openai_base_url: formState.openai_base_url.trim() || "",
                ai_low_risk_model: formState.ai_low_risk_model,
                ai_high_risk_model: formState.ai_high_risk_model,
                ai_timeout_seconds: Number(formState.ai_timeout_seconds),
                join_verification_enabled: formState.join_verification_enabled,
                join_verification_timeout_seconds: Number(formState.join_verification_timeout_seconds),
                join_verification_question_type: formState.join_verification_question_type,
                join_verification_max_attempts: Number(formState.join_verification_max_attempts),
                join_verification_whitelist_bypass: formState.join_verification_whitelist_bypass,
                join_welcome_enabled: formState.join_welcome_enabled,
                join_welcome_use_ai: formState.join_welcome_use_ai,
                join_welcome_template: formState.join_welcome_template.trim() || "欢迎 {user} 加入 {chat}，请先阅读群规并友善交流。",
                run_mode: formState.run_mode,
                webhook_public_url: formState.webhook_public_url.trim() || "",
                webhook_path: formState.webhook_path.trim() || "/telegram/webhook",
                redis_url: formState.redis_url.trim() || undefined,
                redis_namespace: formState.redis_namespace.trim() || "tmbot",
              })
            }
          >
            <Save className="mr-2 h-4 w-4" />
            {saving ? "保存中..." : "保存 AI 配置并热生效"}
          </Button>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <Card className="border bg-background/60 shadow-none">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">消息审计测试</CardTitle>
              {chatId ? <Badge variant="outline">Chat {chatId}</Badge> : null}
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">输入一段消息，点击后会真实请求当前 AI 审计模型。</p>
              <Textarea rows={4} value={moderationText} onChange={(e) => setModerationText(e.target.value)} />
              <Button disabled={!canTest || !moderationText.trim() || testingModeration} onClick={() => void handleModerationTest()}>
                <Bot className="mr-2 h-4 w-4" />
                {testingModeration ? "请求中..." : "真实请求一次"}
              </Button>
              {moderationError ? (
                <Alert variant="destructive">
                  <AlertTitle>审计测试失败</AlertTitle>
                  <AlertDescription>{moderationError}</AlertDescription>
                </Alert>
              ) : null}
              {moderationResult ? (
                <ResultTable
                  rows={[
                    ["开关状态", moderationResult.chat_ai_enabled ? "当前聊天 AI 已开启" : "当前聊天 AI 已关闭（本次仍已强制实测）"],
                    ["模型", moderationResult.model || "-"],
                    ["分类", moderationResult.category],
                    ["等级 / 动作", `L${moderationResult.level} / ${moderationResult.suggested_action}`],
                    ["置信度", moderationResult.confidence.toFixed(2)],
                    ["耗时", `${moderationResult.latency_ms} ms`],
                    ["原因", moderationResult.reasons.join("；") || "-"],
                  ]}
                />
              ) : null}
            </CardContent>
          </Card>

          <Card className="border bg-background/60 shadow-none">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">欢迎语测试</CardTitle>
              {chatId ? <Badge variant="outline">Chat {chatId}</Badge> : null}
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">输入一个用户名，点击后会真实请求当前欢迎语 AI。</p>
              <Input value={welcomeUserDisplayName} onChange={(e) => setWelcomeUserDisplayName(e.target.value)} />
              <Button disabled={!canTest || !welcomeUserDisplayName.trim() || testingWelcome} onClick={() => void handleWelcomeTest()}>
                <Sparkles className="mr-2 h-4 w-4" />
                {testingWelcome ? "请求中..." : "真实请求一次"}
              </Button>
              {welcomeError ? (
                <Alert variant="destructive">
                  <AlertTitle>欢迎语测试失败</AlertTitle>
                  <AlertDescription>{welcomeError}</AlertDescription>
                </Alert>
              ) : null}
              {welcomeResult ? (
                <ResultTable
                  rows={[
                    ["欢迎语开关", welcomeResult.join_welcome_enabled ? "已开启" : "已关闭（本次仍已强制实测）"],
                    ["欢迎语 AI", welcomeResult.join_welcome_use_ai ? "已开启" : "已关闭（本次仍已强制实测）"],
                    ["模型", welcomeResult.model],
                    ["耗时", `${welcomeResult.latency_ms} ms`],
                    ["模板", welcomeResult.template],
                    ["结果", welcomeResult.text],
                  ]}
                />
              ) : null}
            </CardContent>
          </Card>
        </div>

        <VerificationQuestionPanel
          chatId={chatId}
          loading={questionsLoading}
          generating={questionsGenerating}
          questionType={config?.join_verification_question_type ?? "button"}
          questions={verificationQuestions}
          onCreate={onCreateQuestion}
          onUpdate={onUpdateQuestion}
          onDelete={onDeleteQuestion}
          onGenerate={onGenerateQuestions}
        />
      </CardContent>
    </Card>
  );
}
