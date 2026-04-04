import { useEffect, useMemo, useState } from "react";
import { 
  CheckCircle2, 
  Circle, 
  ChevronRight, 
  Bot, 
  KeyRound, 
  Rocket,
  RotateCcw,
  Settings2, 
  Server, 
  ShieldCheck, 
  Wifi,
  Sparkles,
  Zap,
  RefreshCw,
  AlertTriangle
} from "lucide-react";
import { ApiClient } from "@/lib/api";
import { getErrorMessage } from "@/lib/helpers";
import { cn } from "@/lib/utils";

// shadcn UI
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThemeToggle } from "@/components/ui/theme-toggle";

type Props = {
  baseUrl: string;
  frontendVersion: string;
  backendVersion: string;
  onBaseUrlChange: (value: string) => void;
  onActivated: (adminToken: string) => Promise<unknown> | void;
};

type SetupFormValues = {
  bot_token: string;
  openai_api_key: string;
  openai_base_url?: string;
  admin_api_token: string;
  run_mode: "polling" | "webhook";
  webhook_public_url?: string;
  ai_low_risk_model: string;
  ai_high_risk_model: string;
  join_verification_enabled: boolean;
  join_verification_timeout_seconds: number;
  join_verification_question_type: "button" | "quiz";
  join_verification_max_attempts: number;
  join_verification_whitelist_bypass: boolean;
  join_welcome_enabled: boolean;
  join_welcome_use_ai: boolean;
  join_welcome_template: string;
};

export function SetupWizardPage({ baseUrl, frontendVersion, backendVersion, onBaseUrlChange, onActivated }: Props) {
  const [draftBaseUrl, setDraftBaseUrl] = useState(baseUrl);
  const effectiveBaseUrl = draftBaseUrl.trim() || baseUrl;
  const api = useMemo(() => new ApiClient(effectiveBaseUrl), [effectiveBaseUrl]);
  
  const [step, setStep] = useState(0);
  const [authCode, setAuthCode] = useState("");
  const [setupToken, setSetupToken] = useState("");
  const [loading, setLoading] = useState(false);
  
  const [formValues, setFormValues] = useState<SetupFormValues>({
    bot_token: "",
    openai_api_key: "",
    openai_base_url: "",
    admin_api_token: "",
    run_mode: "polling",
    ai_low_risk_model: "gpt-4o-mini",
    ai_high_risk_model: "gpt-4o",
    join_verification_enabled: true,
    join_verification_timeout_seconds: 180,
    join_verification_question_type: "button",
    join_verification_max_attempts: 3,
    join_verification_whitelist_bypass: true,
    join_welcome_enabled: true,
    join_welcome_use_ai: true,
    join_welcome_template: "欢迎 {user} 加入 {chat}，请先阅读群规并友善交流。",
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setDraftBaseUrl(baseUrl);
  }, [baseUrl]);

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!formValues.bot_token) newErrors.bot_token = "必填";
    if (!formValues.admin_api_token) newErrors.admin_api_token = "必填";
    if (!formValues.openai_api_key) newErrors.openai_api_key = "必填";
    if (formValues.run_mode === "webhook" && !formValues.webhook_public_url) {
      newErrors.webhook_public_url = "Webhook 模式必须填写公网地址";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const doAuth = async () => {
    if (!authCode.trim()) return;
    setLoading(true);
    try {
      const out = await api.setupAuth(authCode.trim());
      onBaseUrlChange(effectiveBaseUrl);
      setSetupToken(out.setup_token);
      setStep(1);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const reissueCode = async () => {
    setLoading(true);
    try {
      const out = await api.setupReissueCode();
      onBaseUrlChange(effectiveBaseUrl);
      setAuthCode(out.code);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const saveAndActivate = async () => {
    if (!setupToken) return;
    if (!validate()) return;
    
    setLoading(true);
    try {
      await api.setupConfig(setupToken, formValues);
      await api.setupActivate(setupToken);
      onBaseUrlChange(effectiveBaseUrl);
      await onActivated(formValues.admin_api_token);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    { title: "身份验证", icon: ShieldCheck },
    { title: "核心配置", icon: Settings2 },
    { title: "激活运行", icon: Zap },
  ];

  return (
    <div className="setup-page min-h-screen flex items-center justify-center p-6 bg-muted/30">
      <div className="fixed right-6 top-6 z-50">
        <ThemeToggle className="bg-background/80 backdrop-blur" />
      </div>
      <Card className="w-full max-w-5xl shadow-2xl border-none overflow-hidden">
        <div className="grid lg:grid-cols-[300px_1fr] h-full">
          {/* Left Sidebar Info */}
          <div className="bg-primary p-8 text-primary-foreground flex flex-col justify-between hidden lg:flex">
            <div className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="bg-white/20 p-2 rounded-lg">
                  <Bot className="h-6 w-6" />
                </div>
                <div>
                  <h2 className="font-bold text-lg leading-tight">首次配置向导</h2>
                  <p className="text-primary-foreground/70 text-xs uppercase tracking-wider font-medium">Setup Wizard</p>
                </div>
              </div>
              
              <div className="space-y-8 mt-12">
                {steps.map((s, i) => (
                  <div key={i} className={cn("flex items-center gap-4 transition-opacity", step < i && "opacity-40")}>
                    <div className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-full border-2",
                      step > i ? "bg-white border-white text-primary" : "border-white/50"
                    )}>
                      {step > i ? <CheckCircle2 className="h-5 w-5" /> : <span className="text-xs font-bold">{i + 1}</span>}
                    </div>
                    <span className={cn("font-medium", step === i ? "text-white" : "text-white/70")}>{s.title}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="bg-white/10 border-white/20 text-white">前端 v{frontendVersion}</Badge>
                <Badge variant="outline" className="bg-white/10 border-white/20 text-white">后端 v{backendVersion}</Badge>
              </div>
              <p className="text-xs text-primary-foreground/60 leading-relaxed">
                终端只负责安装与启动，业务配置全部在这里完成。激活后您将进入功能齐全的管理后台。
              </p>
            </div>
          </div>

          {/* Right Content Area */}
          <div className="bg-card flex flex-col h-full overflow-hidden">
            <CardHeader className="border-b lg:hidden px-6 py-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xl font-bold">配置向导</CardTitle>
                <div className="flex gap-2">
                  <Badge>v{frontendVersion}</Badge>
                </div>
              </div>
            </CardHeader>

            <ScrollArea className="flex-1">
              <div className="p-8">
                {step === 0 && (
                  <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-500">
                    <div className="space-y-2">
                      <h3 className="text-xl font-bold">连接后端与口令验证</h3>
                      <p className="text-muted-foreground text-sm">请输入您的后端 API 地址和终端显示的首次启动口令。</p>
                    </div>

                    <div className="grid gap-6">
                      <div className="space-y-2">
                        <Label htmlFor="base-url" className="flex items-center gap-2">
                          <Wifi className="h-4 w-4 text-muted-foreground" />
                          后端地址
                        </Label>
                        <Input 
                          id="base-url" 
                          value={draftBaseUrl} 
                          onChange={(e) => setDraftBaseUrl(e.target.value)} 
                          placeholder="http://127.0.0.1:10010"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="auth-code" className="flex items-center gap-2">
                          <KeyRound className="h-4 w-4 text-muted-foreground" />
                          首次启动口令
                        </Label>
                        <Input 
                          id="auth-code" 
                          value={authCode} 
                          onChange={(e) => setAuthCode(e.target.value)} 
                          placeholder="查看终端输出的口令"
                          className="h-12 text-lg font-mono tracking-wider"
                        />
                      </div>

                      {setupToken && (
                        <Alert className="bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-500/10 dark:border-emerald-400/20 dark:text-emerald-100">
                          <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
                          <AlertTitle>验证成功</AlertTitle>
                          <AlertDescription>身份已确认，点击下方按钮开始配置业务参数。</AlertDescription>
                        </Alert>
                      )}
                    </div>

                    <div className="flex gap-3 pt-4">
                      <Button 
                        size="lg" 
                        className="flex-1 font-bold" 
                        disabled={loading || !authCode} 
                        onClick={doAuth}
                      >
                        {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                        验证口令
                      </Button>
                      <Button variant="outline" size="lg" onClick={reissueCode} disabled={loading}>
                        <RotateCcw className="mr-2 h-4 w-4" />
                        重新生成口令
                      </Button>
                    </div>
                  </div>
                )}

                {step === 1 && (
                  <div className="space-y-8 animate-in fade-in slide-in-from-right-4 duration-500">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-primary">
                        <Settings2 className="h-5 w-5" />
                        <h3 className="text-xl font-bold">运行参数配置</h3>
                      </div>
                      <p className="text-muted-foreground text-sm">这些参数决定了机器人的核心功能，保存后将立即生效。</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
                      <div className="space-y-2">
                        <Label className="text-sm font-semibold">Telegram Bot Token</Label>
                        <Input 
                          value={formValues.bot_token}
                          onChange={(e) => setFormValues({...formValues, bot_token: e.target.value})}
                          placeholder="从 @BotFather 获取"
                          className={cn(errors.bot_token && "border-destructive")}
                        />
                        {errors.bot_token && <p className="text-[10px] text-destructive font-medium">{errors.bot_token}</p>}
                      </div>

                      <div className="space-y-2">
                        <Label className="text-sm font-semibold">管理 API Token</Label>
                        <Input 
                          type="password"
                          value={formValues.admin_api_token}
                          onChange={(e) => setFormValues({...formValues, admin_api_token: e.target.value})}
                          placeholder="自定义用于登录后台的口令"
                          className={cn(errors.admin_api_token && "border-destructive")}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-sm font-semibold">OpenAI/兼容平台 API Key</Label>
                        <Input 
                          type="password"
                          value={formValues.openai_api_key}
                          onChange={(e) => setFormValues({...formValues, openai_api_key: e.target.value})}
                          placeholder="sk-..."
                          className={cn(errors.openai_api_key && "border-destructive")}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-sm font-semibold">API Base URL</Label>
                        <Input 
                          value={formValues.openai_base_url}
                          onChange={(e) => setFormValues({...formValues, openai_base_url: e.target.value})}
                          placeholder="留空使用官方地址"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-sm font-semibold">低风险检查模型</Label>
                        <Input 
                          value={formValues.ai_low_risk_model}
                          onChange={(e) => setFormValues({...formValues, ai_low_risk_model: e.target.value})}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-sm font-semibold">高风险决策模型</Label>
                        <Input 
                          value={formValues.ai_high_risk_model}
                          onChange={(e) => setFormValues({...formValues, ai_high_risk_model: e.target.value})}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-sm font-semibold">运行模式</Label>
                        <Select 
                          value={formValues.run_mode} 
                          onValueChange={(val: any) => setFormValues({...formValues, run_mode: val})}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="polling">Polling (长轮询)</SelectItem>
                            <SelectItem value="webhook">Webhook (回调)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {formValues.run_mode === "webhook" && (
                        <div className="space-y-2">
                          <Label className="text-sm font-semibold text-primary italic">Webhook 公网 URL</Label>
                          <Input 
                            value={formValues.webhook_public_url}
                            onChange={(e) => setFormValues({...formValues, webhook_public_url: e.target.value})}
                            placeholder="https://your-domain.com"
                            className={cn(errors.webhook_public_url && "border-destructive")}
                          />
                        </div>
                      )}
                    </div>

                    <Separator />

                    <div className="space-y-6">
                      <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border">
                        <div className="space-y-0.5">
                          <Label className="text-base font-bold flex items-center gap-2">
                            <ShieldCheck className="h-4 w-4 text-primary" />
                            入群验证 (Join Verification)
                          </Label>
                          <p className="text-xs text-muted-foreground">新成员加入群组时需完成的人机验证。</p>
                        </div>
                        <Switch 
                          checked={formValues.join_verification_enabled} 
                          onCheckedChange={(val) => setFormValues({...formValues, join_verification_enabled: val})}
                        />
                      </div>

                      {formValues.join_verification_enabled && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-4 border-l-2 border-primary/20">
                          <div className="space-y-1.5">
                            <Label className="text-xs font-semibold">超时时长 (秒)</Label>
                            <Input 
                              type="number" 
                              value={formValues.join_verification_timeout_seconds}
                              onChange={(e) => setFormValues({...formValues, join_verification_timeout_seconds: parseInt(e.target.value)})}
                            />
                          </div>
                          <div className="space-y-1.5">
                            <Label className="text-xs font-semibold">验证类型</Label>
                            <Select 
                              value={formValues.join_verification_question_type} 
                              onValueChange={(val: any) => setFormValues({...formValues, join_verification_question_type: val})}
                            >
                              <SelectTrigger className="h-9 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="button">按钮点击验证</SelectItem>
                                <SelectItem value="quiz">智能题库验证</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border">
                        <div className="space-y-0.5">
                          <Label className="text-base font-bold flex items-center gap-2">
                            <Sparkles className="h-4 w-4 text-amber-500" />
                            AI 欢迎语 (Welcome AI)
                          </Label>
                          <p className="text-xs text-muted-foreground">成员通过验证后，自动生成并发送的欢迎消息。</p>
                        </div>
                        <Switch 
                          checked={formValues.join_welcome_enabled} 
                          onCheckedChange={(val) => setFormValues({...formValues, join_welcome_enabled: val})}
                        />
                      </div>

                      {formValues.join_welcome_enabled && (
                        <div className="space-y-3 pl-4 border-l-2 border-amber-500/20">
                          <div className="flex items-center gap-2">
                            <Switch 
                              id="welcome-ai"
                              checked={formValues.join_welcome_use_ai} 
                              onCheckedChange={(val) => setFormValues({...formValues, join_welcome_use_ai: val})}
                            />
                            <Label htmlFor="welcome-ai" className="text-xs font-medium">使用 AI 个性化生成欢迎语</Label>
                          </div>
                          <div className="space-y-1.5">
                            <Label className="text-xs font-semibold">消息模板</Label>
                            <Textarea 
                              rows={3}
                              value={formValues.join_welcome_template}
                              onChange={(e) => setFormValues({...formValues, join_welcome_template: e.target.value})}
                              placeholder="支持 {user} 和 {chat} 占位符"
                              className="text-sm"
                            />
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="pt-6">
                      <Button 
                        size="lg" 
                        className="w-full font-bold shadow-xl shadow-primary/20 h-12" 
                        disabled={loading}
                        onClick={saveAndActivate}
                      >
                        {loading ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
                        完成并激活系统
                      </Button>
                      <p className="text-center text-[10px] text-muted-foreground mt-4 italic">
                        点击激活后，系统将进行最后的安全性校验并热重启服务。
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        </div>
      </Card>
    </div>
  );
}
