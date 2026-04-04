import { useEffect, useState } from "react";
import { KeyRound, LogIn, Server, ShieldAlert } from "lucide-react";
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
import { ThemeToggle } from "@/components/ui/theme-toggle";

type Props = {
  baseUrl: string;
  onBaseUrlChange: (value: string) => void;
  adminToken: string;
  frontendVersion: string;
  backendVersion: string;
  loading: boolean;
  errorMessage?: string;
  onLogin: (adminToken: string) => void;
};

export function AdminLoginPage({
  baseUrl,
  onBaseUrlChange,
  adminToken,
  frontendVersion,
  backendVersion,
  loading,
  errorMessage,
  onLogin,
}: Props) {
  const [draftBaseUrl, setDraftBaseUrl] = useState(baseUrl);
  const [draftToken, setDraftToken] = useState(adminToken);

  useEffect(() => setDraftBaseUrl(baseUrl), [baseUrl]);
  useEffect(() => setDraftToken(adminToken), [adminToken]);

  const submitLogin = () => {
    onBaseUrlChange(draftBaseUrl.trim() || baseUrl);
    onLogin(draftToken);
  };

  return (
    <div className="auth-page flex items-center justify-center min-h-screen p-4">
      <div className="fixed right-6 top-6 z-50">
        <ThemeToggle className="bg-background/80 backdrop-blur" />
      </div>
      <Card className="w-full max-w-[480px] shadow-2xl border-none">
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary" className="bg-blue-50 text-blue-700 hover:bg-blue-50 dark:bg-cyan-500/15 dark:text-cyan-200 dark:hover:bg-cyan-500/20">
              前端 v{frontendVersion}
            </Badge>
            <Badge variant="secondary" className="bg-slate-50 text-slate-700 hover:bg-slate-50 dark:bg-slate-500/15 dark:text-slate-200 dark:hover:bg-slate-500/20">
              后端 v{backendVersion}
            </Badge>
          </div>
          <div className="space-y-1">
            <CardTitle className="text-2xl font-bold tracking-tight">管理后台登录</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              输入管理令牌后进入控制台。登录成功后会自动记住当前会话。
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {errorMessage && (
            <Alert variant="destructive" className="animate-in fade-in zoom-in duration-300">
              <ShieldAlert className="h-4 w-4" />
              <AlertTitle>登录失败</AlertTitle>
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="base-url" className="text-sm font-semibold flex items-center gap-2">
                <Server className="h-4 w-4 text-muted-foreground" />
                API 地址
              </Label>
              <Input
                id="base-url"
                value={draftBaseUrl}
                onChange={(e) => setDraftBaseUrl(e.target.value)}
                placeholder="http://127.0.0.1:10010"
                className="h-11"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="admin-token" className="text-sm font-semibold flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-muted-foreground" />
                管理令牌
              </Label>
              <Input
                id="admin-token"
                type="password"
                value={draftToken}
                onChange={(e) => setDraftToken(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submitLogin()}
                placeholder="请输入管理 API Token"
                className="h-11"
              />
            </div>
          </div>
        </CardContent>
        <CardFooter>
          <Button 
            className="w-full h-11 text-base font-bold shadow-lg shadow-primary/20 transition-all hover:translate-y-[-1px] active:translate-y-[0px]" 
            disabled={loading}
            onClick={submitLogin}
          >
            <LogIn className="mr-2 h-4 w-4" />
            {loading ? "正在验证..." : "登录后台"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
