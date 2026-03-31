import { useEffect, useState } from "react";
import { Button, Card, Col, Input, Row, Select, Space, Tag, Typography } from "antd";
import type { KnownChat } from "@/lib/api";

type Props = {
  baseUrl: string;
  chatId: string;
  knownChats: KnownChat[];
  onReloadChats: () => Promise<void>;
  onSaveConnection: (values: { baseUrl: string; chatId: string }) => void;
  runtimeState: "setup" | "active";
  lastSyncText: string;
};

export function SystemSettingsPanel({
  baseUrl,
  chatId,
  knownChats,
  onReloadChats,
  onSaveConnection,
  runtimeState,
  lastSyncText,
}: Props) {
  const [draftBaseUrl, setDraftBaseUrl] = useState(baseUrl);
  const [draftChatId, setDraftChatId] = useState(chatId);

  useEffect(() => setDraftBaseUrl(baseUrl), [baseUrl]);
  useEffect(() => setDraftChatId(chatId), [chatId]);

  return (
    <Card title="系统设置">
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Row gutter={12}>
          <Col xs={24} md={12}>
            <Typography.Text>API 地址</Typography.Text>
            <Input value={draftBaseUrl} onChange={(e) => setDraftBaseUrl(e.target.value)} />
            <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
              管理令牌改为登录页输入，这里只保留服务地址和当前群设置。
            </Typography.Paragraph>
          </Col>
        </Row>
        <Row gutter={12}>
          <Col xs={24} md={12}>
            <Typography.Text>当前 Chat</Typography.Text>
            <Select
              value={draftChatId || undefined}
              style={{ width: "100%" }}
              showSearch
              optionFilterProp="label"
              options={knownChats.map((item) => ({
                value: String(item.chat_id),
                label: `${item.title ?? "未命名群"} (${item.chat_id})`,
              }))}
              onChange={(value) => setDraftChatId(value)}
            />
            <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
              自动获取只会列出机器人已接收到事件的群。首次使用时，先把机器人拉进群；若还没出现，在群里发一条消息或命令后再刷新。
            </Typography.Paragraph>
          </Col>
          <Col xs={24} md={12} style={{ display: "flex", alignItems: "end" }}>
            <Space>
              <Button onClick={() => void onReloadChats()}>自动获取 Chat</Button>
              <Button type="primary" onClick={() => onSaveConnection({ baseUrl: draftBaseUrl, chatId: draftChatId })}>
                保存连接配置
              </Button>
              <Tag color={runtimeState === "active" ? "success" : "default"}>{runtimeState.toUpperCase()}</Tag>
              <Typography.Text type="secondary">最近同步: {lastSyncText}</Typography.Text>
            </Space>
          </Col>
        </Row>
      </Space>
    </Card>
  );
}
