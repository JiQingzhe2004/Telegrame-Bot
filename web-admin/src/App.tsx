import { useEffect, useMemo, useState } from "react";
import { Alert, Flex, Result, Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { ApiClient } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { getErrorMessage, readStorage, writeStorage } from "@/lib/helpers";
import { SetupWizardPage } from "@/pages/SetupWizardPage";
import { AdminConsolePage } from "@/pages/AdminConsolePage";

export function App() {
  const [baseUrl, setBaseUrl] = useState(readStorage("bot_base_url", window.location.origin || "http://127.0.0.1:10010"));
  const api = useMemo(() => new ApiClient(baseUrl), [baseUrl]);

  useEffect(() => {
    writeStorage("bot_base_url", baseUrl);
  }, [baseUrl]);

  const runtimeStateQuery = useQuery({
    queryKey: queryKeys.runtime,
    queryFn: () => api.getRuntimeState(),
    retry: 1,
    refetchInterval: 15000,
  });

  if (runtimeStateQuery.isLoading) {
    return (
      <Flex align="center" justify="center" style={{ height: "100vh" }}>
        <Spin size="large" tip="正在连接服务..." />
      </Flex>
    );
  }

  if (runtimeStateQuery.isError || !runtimeStateQuery.data) {
    return (
      <Result
        status="warning"
        title="无法连接后端服务"
        subTitle={getErrorMessage(runtimeStateQuery.error, "请确认 python -m bot.main 已启动")}
        extra={<Alert type="info" showIcon message="你仍可以先在“系统设置”中调整 API 地址后重试。" />}
      />
    );
  }

  if (runtimeStateQuery.data.state === "setup") {
    return (
      <SetupWizardPage
        baseUrl={baseUrl}
        onBaseUrlChange={setBaseUrl}
        onActivated={() => runtimeStateQuery.refetch()}
      />
    );
  }

  return <AdminConsolePage baseUrl={baseUrl} onBaseUrlChange={setBaseUrl} runtimeState={runtimeStateQuery.data.state} />;
}
