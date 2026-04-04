import { useEffect, useMemo, useState } from "react";
import { AlertCircle, RefreshCw, Server, WifiOff } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { ApiClient } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { FRONTEND_VERSION } from "@/lib/version";
import { getErrorMessage, readStorage, writeStorage } from "@/lib/helpers";
import { SetupWizardPage } from "@/pages/SetupWizardPage";
import { AdminConsolePage } from "@/pages/AdminConsolePage";
import { AdminLoginPage } from "@/pages/AdminLoginPage";

// shadcn UI
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { Label } from "@/components/ui/label";
import { ThemeToggle } from "@/components/ui/theme-toggle";

type ConnectionErrorPageProps = {
  baseUrl: string;
  frontendVersion: string;
  errorMessage: string;
  onRetry: (baseUrl: string) => void;
};

function ConnectionErrorPage({ baseUrl, frontendVersion, errorMessage, onRetry }: ConnectionErrorPageProps) {
  const [draftBaseUrl, setDraftBaseUrl] = useState(baseUrl);
  const hint = (() => {
    const maybe = runtimeErrorFromMessage(errorMessage);
    return maybe?.hint ?? "";
  })();

  useEffect(() => {
    setDraftBaseUrl(baseUrl);
  }, [baseUrl]);

  return (
    <div className="auth-page flex items-center justify-center min-h-screen p-4">
      <div className="fixed right-6 top-6 z-50">
        <ThemeToggle className="bg-background/80 backdrop-blur" />
      </div>
      <Card className="w-full max-w-[520px] shadow-2xl border-none">
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary" className="bg-blue-50 text-blue-700 hover:bg-blue-50 dark:bg-cyan-500/15 dark:text-cyan-200 dark:hover:bg-cyan-500/20">
              前端 v{frontendVersion}
            </Badge>
            <Badge variant="destructive" className="animate-pulse">
              后端未连接
            </Badge>
          </div>
          <div className="space-y-1">
            <CardTitle className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <WifiOff className="h-6 w-6 text-destructive" />
              无法连接后端服务
            </CardTitle>
            <CardDescription>
              请检查后端服务是否已启动，并确认 API 地址配置是否正确。
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>连接异常</AlertTitle>
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>

          {hint && (
            <Alert className="bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-500/10 dark:border-amber-400/20 dark:text-amber-100">
              <AlertTitle className="text-amber-800 font-bold dark:text-amber-200">排查提示</AlertTitle>
              <AlertDescription className="whitespace-pre-line text-amber-700 dark:text-amber-200/90">
                {hint}
              </AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            <Label htmlFor="api-url" className="text-sm font-semibold flex items-center gap-2">
              <Server className="h-4 w-4 text-muted-foreground" />
              API 地址
            </Label>
            <Input
              id="api-url"
              value={draftBaseUrl}
              onChange={(e) => setDraftBaseUrl(e.target.value)}
              placeholder="http://127.0.0.1:10010"
              className="h-11"
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button 
            className="w-full h-11 text-base font-bold flex items-center gap-2"
            onClick={() => onRetry(draftBaseUrl.trim() || baseUrl)}
          >
            <RefreshCw className="h-4 w-4" />
            重新尝试连接
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

function runtimeErrorFromMessage(_message: string): { hint?: string } | null {
  const anyWin = window as unknown as { __BOT_LAST_ERROR?: unknown };
  const err = anyWin.__BOT_LAST_ERROR;
  if (!err || typeof err !== "object") return null;
  const maybe = err as { hint?: string };
  return maybe.hint ? maybe : null;
}

export function App() {
  const [baseUrl, setBaseUrl] = useState(readStorage("bot_base_url", window.location.origin || "http://127.0.0.1:10010"));
  const [adminToken, setAdminToken] = useState(readStorage("bot_admin_token"));
  const [loginErrorMessage, setLoginErrorMessage] = useState("");
  const [runtimeAttempt, setRuntimeAttempt] = useState(0);
  const [loginAttempt, setLoginAttempt] = useState(0);
  const api = useMemo(() => new ApiClient(baseUrl), [baseUrl]);

  useEffect(() => {
    writeStorage("bot_base_url", baseUrl);
  }, [baseUrl]);

  const runtimeStateQuery = useQuery({
    queryKey: [...queryKeys.runtime(baseUrl), runtimeAttempt],
    queryFn: () => api.getRuntimeState(),
    retry: 1,
    refetchOnWindowFocus: false,
  });
  const adminSessionQuery = useQuery({
    queryKey: [...queryKeys.adminSession(baseUrl, adminToken), loginAttempt],
    queryFn: () => api.login(adminToken),
    enabled: runtimeStateQuery.data?.state === "active" && Boolean(adminToken),
    retry: false,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (adminSessionQuery.isSuccess && adminToken) {
      writeStorage("bot_admin_token", adminToken);
      setLoginErrorMessage("");
    }
  }, [adminSessionQuery.isSuccess, adminToken]);

  useEffect(() => {
    if (!adminSessionQuery.isError) return;
    localStorage.removeItem("bot_admin_token");
    setLoginErrorMessage(getErrorMessage(adminSessionQuery.error, "管理令牌校验失败"));
  }, [adminSessionQuery.error, adminSessionQuery.isError]);

  useEffect(() => {
    setLoginErrorMessage("");
  }, [baseUrl]);

  const handleLogin = (nextAdminToken: string) => {
    const trimmedToken = nextAdminToken.trim();
    if (!trimmedToken) {
      setLoginErrorMessage("请输入管理令牌");
      return;
    }
    setLoginErrorMessage("");
    setAdminToken(trimmedToken);
    setLoginAttempt((value) => value + 1);
  };

  const handleLogout = () => {
    setAdminToken("");
    setLoginErrorMessage("");
    localStorage.removeItem("bot_admin_token");
  };

  const handleRetryConnection = (nextBaseUrl: string) => {
    setBaseUrl(nextBaseUrl);
    setRuntimeAttempt((value) => value + 1);
  };

  if (runtimeStateQuery.isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <RefreshCw className="h-10 w-10 text-primary animate-spin" />
        <span className="text-sm font-medium text-muted-foreground">正在连接服务...</span>
      </div>
    );
  }

  if (runtimeStateQuery.isError || !runtimeStateQuery.data) {
    (window as unknown as { __BOT_LAST_ERROR?: unknown }).__BOT_LAST_ERROR = runtimeStateQuery.error;
    return (
      <ConnectionErrorPage
        baseUrl={baseUrl}
        frontendVersion={FRONTEND_VERSION}
        errorMessage={getErrorMessage(runtimeStateQuery.error, "请确认 python -m bot.main 已启动")}
        onRetry={handleRetryConnection}
      />
    );
  }

  if (runtimeStateQuery.data.state === "setup") {
    return (
      <SetupWizardPage
        baseUrl={baseUrl}
        frontendVersion={FRONTEND_VERSION}
        backendVersion={runtimeStateQuery.data.backend_version}
        onBaseUrlChange={setBaseUrl}
        onActivated={(nextAdminToken) => {
          setAdminToken(nextAdminToken.trim());
          setLoginErrorMessage("");
          setLoginAttempt((value) => value + 1);
          return runtimeStateQuery.refetch();
        }}
      />
    );
  }

  if (!adminToken || adminSessionQuery.isError || adminSessionQuery.data?.authenticated === false) {
    return (
      <AdminLoginPage
        baseUrl={baseUrl}
        onBaseUrlChange={setBaseUrl}
        adminToken={adminToken}
        frontendVersion={FRONTEND_VERSION}
        backendVersion={runtimeStateQuery.data.backend_version}
        loading={adminSessionQuery.isFetching}
        errorMessage={loginErrorMessage || undefined}
        onLogin={handleLogin}
      />
    );
  }

  if (adminSessionQuery.isLoading || adminSessionQuery.isFetching || !adminSessionQuery.data) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <RefreshCw className="h-10 w-10 text-primary animate-spin" />
        <span className="text-sm font-medium text-muted-foreground">正在验证管理令牌...</span>
      </div>
    );
  }

  return (
    <AdminConsolePage
      baseUrl={baseUrl}
      onBaseUrlChange={setBaseUrl}
      runtimeState={runtimeStateQuery.data.state}
      adminToken={adminToken}
      frontendVersion={FRONTEND_VERSION}
      backendVersion={adminSessionQuery.data.backend_version}
      onLogout={handleLogout}
    />
  );
}
