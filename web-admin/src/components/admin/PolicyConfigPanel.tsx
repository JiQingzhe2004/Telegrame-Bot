import { Button, Card, Form, InputNumber, Select, Space, Switch } from "antd";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import type { ChatSettings } from "@/lib/api";

type Props = {
  data: AdminDataBundle;
  actions: AdminActions;
};

export function PolicyConfigPanel({ data, actions }: Props) {
  const settings = data.settings;

  const apply = async (payload: Partial<ChatSettings>) => {
    await actions.updateSettings(payload);
  };

  return (
    <Card title="策略配置" loading={data.isLoading}>
      <Form layout="vertical" initialValues={settings}>
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Form.Item label="模式">
            <Select
              value={settings?.mode}
              options={[
                { label: "strict", value: "strict" },
                { label: "balanced", value: "balanced" },
                { label: "relaxed", value: "relaxed" },
              ]}
              onChange={(value) => void apply({ mode: value })}
            />
          </Form.Item>
          <Form.Item label="AI 开关">
            <Switch checked={Boolean(settings?.ai_enabled)} onChange={(value) => void apply({ ai_enabled: value })} />
          </Form.Item>
          <Form.Item label="AI 阈值">
            <InputNumber min={0} max={1} step={0.01} style={{ width: 220 }} value={settings?.ai_threshold} onChange={(value) => void apply({ ai_threshold: Number(value ?? 0.75) })} />
          </Form.Item>
          <Form.Item label="L3 禁言秒数">
            <InputNumber style={{ width: 220 }} value={settings?.level3_mute_seconds} onChange={(value) => void apply({ level3_mute_seconds: Number(value ?? 604800) })} />
          </Form.Item>
          <Button onClick={() => void actions.refreshAll()}>刷新配置</Button>
        </Space>
      </Form>
    </Card>
  );
}
