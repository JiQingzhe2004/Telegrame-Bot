import { useEffect } from "react";
import { Button, Card, Form, InputNumber, Select, Space, Switch } from "antd";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import type { ChatSettings } from "@/lib/api";

type Props = {
  data: AdminDataBundle;
  actions: AdminActions;
};

export function PolicyConfigPanel({ data, actions }: Props) {
  const settings = data.settings;
  const [form] = Form.useForm<
    Pick<ChatSettings, "mode" | "ai_enabled" | "ai_threshold" | "allow_admin_self_test" | "level3_mute_seconds">
  >();

  useEffect(() => {
    if (!settings) return;
    form.setFieldsValue({
      mode: settings.mode,
      ai_enabled: settings.ai_enabled,
      ai_threshold: settings.ai_threshold,
      allow_admin_self_test: settings.allow_admin_self_test,
      level3_mute_seconds: settings.level3_mute_seconds,
    });
  }, [settings, form]);

  const onSubmit = async () => {
    const values = await form.validateFields();
    await actions.updateSettings(values);
  };

  return (
    <Card title="策略配置" loading={data.isLoading}>
      <Form form={form} layout="vertical">
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Form.Item label="模式" name="mode" rules={[{ required: true, message: "请选择模式" }]}>
            <Select
              options={[
                { label: "strict", value: "strict" },
                { label: "balanced", value: "balanced" },
                { label: "relaxed", value: "relaxed" },
              ]}
            />
          </Form.Item>
          <Form.Item label="AI 开关" name="ai_enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="AI 阈值" name="ai_threshold" rules={[{ required: true, message: "请填写阈值" }]}>
            <InputNumber min={0} max={1} step={0.01} style={{ width: 220 }} />
          </Form.Item>
          <Form.Item
            label="管理员自测模式"
            name="allow_admin_self_test"
            valuePropName="checked"
            extra="开启后，管理员消息也会进入 AI/审计链路，但不会执行真实删除、禁言、封禁。"
          >
            <Switch />
          </Form.Item>
          <Form.Item label="L3 禁言秒数" name="level3_mute_seconds" rules={[{ required: true, message: "请填写秒数" }]}>
            <InputNumber min={1} style={{ width: 220 }} />
          </Form.Item>
          <Space>
            <Button type="primary" onClick={() => void onSubmit()}>
              保存策略配置
            </Button>
            <Button onClick={() => void actions.refreshAll()}>刷新配置</Button>
          </Space>
        </Space>
      </Form>
    </Card>
  );
}
