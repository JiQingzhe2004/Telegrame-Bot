import { useEffect, useState } from "react";
import { Alert, Button, Card, Input, Space, Tag, Typography } from "antd";

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
    <div className="auth-page">
      <Card className="auth-shell-card" style={{ maxWidth: 520, margin: "48px auto" }}>
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <Space size={10} wrap>
            <Tag color="blue">前端 v{frontendVersion}</Tag>
            <Tag color="geekblue">后端 v{backendVersion}</Tag>
          </Space>
          <div>
            <Typography.Title level={3} style={{ marginBottom: 8 }}>
              管理后台登录
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              输入管理令牌后进入控制台。API 地址可在这里直接切换，登录成功后会自动记住当前会话。
            </Typography.Paragraph>
          </div>
          {errorMessage ? <Alert type="error" showIcon message={errorMessage} /> : null}
          <div>
            <Typography.Text strong>API 地址</Typography.Text>
            <Input value={draftBaseUrl} onChange={(e) => setDraftBaseUrl(e.target.value)} placeholder="http://127.0.0.1:10010" />
          </div>
          <div>
            <Typography.Text strong>管理令牌</Typography.Text>
            <Input.Password
              value={draftToken}
              onChange={(e) => setDraftToken(e.target.value)}
              onPressEnter={submitLogin}
              placeholder="请输入管理 API Token"
            />
          </div>
          <Button type="primary" size="large" loading={loading} onClick={submitLogin}>
            登录后台
          </Button>
        </Space>
      </Card>
    </div>
  );
}
