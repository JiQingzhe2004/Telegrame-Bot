import { Button, Card, Col, Input, Row, Select, Space, Tag, Typography } from "antd";
import type { KnownChat } from "@/lib/api";

type Props = {
  baseUrl: string;
  setBaseUrl: (value: string) => void;
  adminToken: string;
  setAdminToken: (value: string) => void;
  chatId: string;
  setChatId: (value: string) => void;
  knownChats: KnownChat[];
  onReloadChats: () => Promise<void>;
  runtimeState: "setup" | "active";
  lastSyncText: string;
};

export function SystemSettingsPanel({
  baseUrl,
  setBaseUrl,
  adminToken,
  setAdminToken,
  chatId,
  setChatId,
  knownChats,
  onReloadChats,
  runtimeState,
  lastSyncText,
}: Props) {
  return (
    <Card title="系统设置">
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Row gutter={12}>
          <Col xs={24} md={12}>
            <Typography.Text>API 地址</Typography.Text>
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </Col>
          <Col xs={24} md={12}>
            <Typography.Text>管理令牌</Typography.Text>
            <Input.Password value={adminToken} onChange={(e) => setAdminToken(e.target.value)} />
          </Col>
        </Row>
        <Row gutter={12}>
          <Col xs={24} md={12}>
            <Typography.Text>当前 Chat</Typography.Text>
            <Select
              value={chatId || undefined}
              style={{ width: "100%" }}
              showSearch
              optionFilterProp="label"
              options={knownChats.map((item) => ({
                value: String(item.chat_id),
                label: `${item.title ?? "未命名群"} (${item.chat_id})`,
              }))}
              onChange={(value) => setChatId(value)}
            />
          </Col>
          <Col xs={24} md={12} style={{ display: "flex", alignItems: "end" }}>
            <Space>
              <Button onClick={() => void onReloadChats()}>自动获取 Chat</Button>
              <Tag color={runtimeState === "active" ? "success" : "default"}>{runtimeState.toUpperCase()}</Tag>
              <Typography.Text type="secondary">最近同步: {lastSyncText}</Typography.Text>
            </Space>
          </Col>
        </Row>
      </Space>
    </Card>
  );
}
