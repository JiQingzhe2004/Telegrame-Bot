import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Descriptions, Form, Input, InputNumber, Row, Select, Space, Switch, Tag, Typography } from "antd";
import type { ModerationAiTestResult, RuntimeConfigPublic, WelcomeAiTestResult } from "@/lib/api";

type Props = {
  config?: RuntimeConfigPublic;
  loading: boolean;
  saving: boolean;
  chatId?: string;
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
  onTestModeration: (text: string) => Promise<ModerationAiTestResult>;
  onTestWelcome: (userDisplayName: string) => Promise<WelcomeAiTestResult>;
};

export function AiConfigPanel({ config, loading, saving, chatId, onSave, onTestModeration, onTestWelcome }: Props) {
  const [form] = Form.useForm();
  const [moderationText, setModerationText] = useState("这是一条 AI 审计测试消息。");
  const [welcomeUserDisplayName, setWelcomeUserDisplayName] = useState("测试用户");
  const [testingModeration, setTestingModeration] = useState(false);
  const [testingWelcome, setTestingWelcome] = useState(false);
  const [moderationResult, setModerationResult] = useState<ModerationAiTestResult | null>(null);
  const [welcomeResult, setWelcomeResult] = useState<WelcomeAiTestResult | null>(null);
  const [moderationError, setModerationError] = useState("");
  const [welcomeError, setWelcomeError] = useState("");

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

  const canTest = Boolean(chatId);

  const handleModerationTest = async () => {
    if (!moderationText.trim()) return;
    setTestingModeration(true);
    setModerationError("");
    try {
      const result = await onTestModeration(moderationText.trim());
      setModerationResult(result);
    } catch (error) {
      setModerationResult(null);
      setModerationError(error instanceof Error ? error.message : "AI 审计测试失败");
    } finally {
      setTestingModeration(false);
    }
  };

  const handleWelcomeTest = async () => {
    if (!welcomeUserDisplayName.trim()) return;
    setTestingWelcome(true);
    setWelcomeError("");
    try {
      const result = await onTestWelcome(welcomeUserDisplayName.trim());
      setWelcomeResult(result);
    } catch (error) {
      setWelcomeResult(null);
      setWelcomeError(error instanceof Error ? error.message : "欢迎语测试失败");
    } finally {
      setTestingWelcome(false);
    }
  };

  return (
    <Card title="AI 配置" loading={loading}>
      <Space direction="vertical" style={{ width: "100%" }} size={16}>
        <Alert
          type="info"
          showIcon
          message="这里保存后会自动热生效，无需重启进程。Key 为空时表示不改动已有值。"
        />
        {!canTest ? <Alert type="warning" showIcon message="未选择 Chat，暂时无法发起真实 AI 测试。" /> : null}
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
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={12}>
            <Card size="small" title="消息审计测试" extra={chatId ? <Tag color="blue">Chat {chatId}</Tag> : null}>
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Typography.Text type="secondary">输入一段消息，点击后会真实请求当前 AI 审计模型。</Typography.Text>
                <Input.TextArea rows={4} value={moderationText} onChange={(e) => setModerationText(e.target.value)} />
                <Button type="primary" loading={testingModeration} disabled={!canTest || !moderationText.trim()} onClick={() => void handleModerationTest()}>
                  真实请求一次
                </Button>
                {moderationError ? <Alert type="error" showIcon message={moderationError} /> : null}
                {moderationResult ? (
                  <Descriptions bordered size="small" column={1}>
                    <Descriptions.Item label="开关状态">{moderationResult.chat_ai_enabled ? "当前聊天 AI 已开启" : "当前聊天 AI 已关闭（本次仍已强制实测）"}</Descriptions.Item>
                    <Descriptions.Item label="模型">{moderationResult.model || "-"}</Descriptions.Item>
                    <Descriptions.Item label="分类">{moderationResult.category}</Descriptions.Item>
                    <Descriptions.Item label="等级 / 动作">
                      L{moderationResult.level} / {moderationResult.suggested_action}
                    </Descriptions.Item>
                    <Descriptions.Item label="置信度">{moderationResult.confidence.toFixed(2)}</Descriptions.Item>
                    <Descriptions.Item label="耗时">{moderationResult.latency_ms} ms</Descriptions.Item>
                    <Descriptions.Item label="原因">{moderationResult.reasons.join("；") || "-"}</Descriptions.Item>
                  </Descriptions>
                ) : null}
              </Space>
            </Card>
          </Col>
          <Col xs={24} xl={12}>
            <Card size="small" title="欢迎语测试" extra={chatId ? <Tag color="purple">Chat {chatId}</Tag> : null}>
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Typography.Text type="secondary">输入一个用户名，点击后会真实请求当前欢迎语 AI。</Typography.Text>
                <Input value={welcomeUserDisplayName} onChange={(e) => setWelcomeUserDisplayName(e.target.value)} />
                <Button type="primary" loading={testingWelcome} disabled={!canTest || !welcomeUserDisplayName.trim()} onClick={() => void handleWelcomeTest()}>
                  真实请求一次
                </Button>
                {welcomeError ? <Alert type="error" showIcon message={welcomeError} /> : null}
                {welcomeResult ? (
                  <Descriptions bordered size="small" column={1}>
                    <Descriptions.Item label="欢迎语开关">
                      {welcomeResult.join_welcome_enabled ? "已开启" : "已关闭（本次仍已强制实测）"}
                    </Descriptions.Item>
                    <Descriptions.Item label="欢迎语 AI">
                      {welcomeResult.join_welcome_use_ai ? "已开启" : "已关闭（本次仍已强制实测）"}
                    </Descriptions.Item>
                    <Descriptions.Item label="模型">{welcomeResult.model}</Descriptions.Item>
                    <Descriptions.Item label="耗时">{welcomeResult.latency_ms} ms</Descriptions.Item>
                    <Descriptions.Item label="模板">{welcomeResult.template}</Descriptions.Item>
                    <Descriptions.Item label="结果">{welcomeResult.text}</Descriptions.Item>
                  </Descriptions>
                ) : null}
              </Space>
            </Card>
          </Col>
        </Row>
      </Space>
    </Card>
  );
}
