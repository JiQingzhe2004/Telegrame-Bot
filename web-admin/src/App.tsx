import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Flex, Input, Space, Spin, Tag, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { ApiClient } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { FRONTEND_VERSION } from "@/lib/version";
import { getErrorMessage, readStorage, writeStorage } from "@/lib/helpers";
import { SetupWizardPage } from "@/pages/SetupWizardPage";
import { AdminConsolePage } from "@/pages/AdminConsolePage";
import { AdminLoginPage } from "@/pages/AdminLoginPage";

type ConnectionErrorPageProps = {
  baseUrl: string;
  frontendVersion: string;
  errorMessage: string;
  onRetry: (baseUrl: string) => void;
};

function ConnectionErrorPage({ baseUrl, frontendVersion, errorMessage, onRetry }: ConnectionErrorPageProps) {
  const [draftBaseUrl, setDraftBaseUrl] = useState(baseUrl);

  useEffect(() => {
    setDraftBaseUrl(baseUrl);
  }, [baseUrl]);

  return (
    <div className="auth-page">
      <Card className="auth-shell-card" style={{ maxWidth: 520, margin: "48px auto" }}>
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <Space size={10} wrap>
            <Tag color="blue">前端 v{frontendVersion}</Tag>
            <Tag>后端未连接</Tag>
          </Space>
          <div>
            <Typography.Title level={3} style={{ marginBottom: 8 }}>
              无法连接后端服务
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              检查后端是否已启动，再确认 API 地址是否正确。
            </Typography.Paragraph>
          </div>
          <Alert type="error" showIcon message={errorMessage} />
          <div>
            <Typography.Text strong>API 地址</Typography.Text>
            <Input value={draftBaseUrl} onChange={(e) => setDraftBaseUrl(e.target.value)} placeholder="http://127.0.0.1:10010" />
          </div>
          <Button type="primary" size="large" onClick={() => onRetry(draftBaseUrl.trim() || baseUrl)}>
            重新连接
          </Button>
        </Space>
      </Card>
    </div>
  );
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
      <Flex align="center" justify="center" style={{ height: "100vh" }}>
        <Spin size="large" tip="正在连接服务..." />
      </Flex>
    );
  }

  if (runtimeStateQuery.isError || !runtimeStateQuery.data) {
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
      <Flex align="center" justify="center" style={{ height: "100vh" }}>
        <Spin size="large" tip="正在验证管理令牌..." />
      </Flex>
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
