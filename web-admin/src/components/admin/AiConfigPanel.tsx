import { useEffect } from "react";
import { Alert, Button, Card, Col, Form, Input, InputNumber, Row, Select, Space, Switch, Tag } from "antd";
import type { RuntimeConfigPublic } from "@/lib/api";

type Props = {
  config?: RuntimeConfigPublic;
  loading: boolean;
  saving: boolean;
  onSave: (payload: {
    openai_api_key?: string;
    openai_base_url?: string;
    ai_low_risk_model: string;
    ai_high_risk_model: string;
    ai_timeout_seconds: number;
    join_verification_enabled: boolean;
    join_verification_timeout_seconds: number;
    join_welcome_enabled: boolean;
    join_welcome_use_ai: boolean;
    join_welcome_template: string;
    run_mode: "polling" | "webhook";
    webhook_public_url?: string;
    webhook_path?: string;
  }) => Promise<void>;
};

export function AiConfigPanel({ config, loading, saving, onSave }: Props) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (!config) return;
    form.setFieldsValue({
      openai_api_key: "",
      openai_base_url: config.openai_base_url || "",
      ai_low_risk_model: config.ai_low_risk_model,
      ai_high_risk_model: config.ai_high_risk_model,
      ai_timeout_seconds: config.ai_timeout_seconds,
      join_verification_enabled: config.join_verification_enabled,
      join_verification_timeout_seconds: config.join_verification_timeout_seconds,
      join_welcome_enabled: config.join_welcome_enabled,
      join_welcome_use_ai: config.join_welcome_use_ai,
      join_welcome_template: config.join_welcome_template,
      run_mode: config.run_mode,
      webhook_public_url: config.webhook_public_url || "",
      webhook_path: config.webhook_path || "/telegram/webhook",
    });
  }, [config, form]);

  return (
    <Card title="AI 配置" loading={loading}>
      <Space direction="vertical" style={{ width: "100%" }} size={16}>
        <Alert
          type="info"
          showIcon
          message="这里保存后会自动热生效，无需重启进程。Key 为空时表示不改动已有值。"
        />
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Tag color="blue">当前运行模式: {config?.run_mode ?? "-"}</Tag>
          </Col>
          <Col xs={24} md={12}>
            <Tag color="purple">当前 Base URL: {config?.openai_base_url || "官方默认"}</Tag>
          </Col>
        </Row>
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) =>
            onSave({
              openai_api_key: values.openai_api_key?.trim() || undefined,
              openai_base_url: values.openai_base_url?.trim() || "",
              ai_low_risk_model: values.ai_low_risk_model,
              ai_high_risk_model: values.ai_high_risk_model,
              ai_timeout_seconds: Number(values.ai_timeout_seconds),
              join_verification_enabled: Boolean(values.join_verification_enabled),
              join_verification_timeout_seconds: Number(values.join_verification_timeout_seconds),
              join_welcome_enabled: Boolean(values.join_welcome_enabled),
              join_welcome_use_ai: Boolean(values.join_welcome_use_ai),
              join_welcome_template: values.join_welcome_template?.trim() || "欢迎 {user} 加入 {chat}，请先阅读群规并友善交流。",
              run_mode: values.run_mode,
              webhook_public_url: values.webhook_public_url?.trim() || "",
              webhook_path: values.webhook_path?.trim() || "/telegram/webhook",
            })
          }
        >
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="OpenAI/兼容平台 API Key（留空不修改）" name="openai_api_key">
                <Input.Password placeholder="sk-..." />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Base URL（可空）" name="openai_base_url">
                <Input placeholder="https://api.openai.com/v1" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="低风险模型" name="ai_low_risk_model" rules={[{ required: true, message: "必填" }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="高风险模型" name="ai_high_risk_model" rules={[{ required: true, message: "必填" }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="AI 超时（秒）" name="ai_timeout_seconds" rules={[{ required: true, message: "必填" }]}>
                <InputNumber min={1} max={120} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="入群验证开关" name="join_verification_enabled" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="入群验证超时（秒）" name="join_verification_timeout_seconds" rules={[{ required: true, message: "必填" }]}>
                <InputNumber min={30} max={3600} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="欢迎语开关" name="join_welcome_enabled" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="欢迎语使用 AI" name="join_welcome_use_ai" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col xs={24}>
              <Form.Item
                label="欢迎语模板（支持 {user} / {chat}）"
                name="join_welcome_template"
                rules={[{ required: true, message: "必填" }]}
              >
                <Input.TextArea rows={3} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="运行模式" name="run_mode" rules={[{ required: true, message: "必选" }]}>
                <Select
                  options={[
                    { label: "Polling", value: "polling" },
                    { label: "Webhook", value: "webhook" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label="Webhook 公网地址"
                name="webhook_public_url"
                dependencies={["run_mode"]}
                rules={[
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (getFieldValue("run_mode") !== "webhook") return Promise.resolve();
                      if (!value) return Promise.reject(new Error("Webhook 模式必须填写"));
                      return Promise.resolve();
                    },
                  }),
                ]}
              >
                <Input placeholder="https://example.com" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Webhook Path" name="webhook_path">
                <Input placeholder="/telegram/webhook" />
              </Form.Item>
            </Col>
          </Row>
          <Button type="primary" htmlType="submit" loading={saving}>
            保存 AI 配置并热生效
          </Button>
        </Form>
      </Space>
    </Card>
  );
}
