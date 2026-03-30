import { useMemo, useState } from "react";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Col,
  Form,
  Input,
  Row,
  Select,
  Space,
  Steps,
  Typography,
} from "antd";
import { ApiClient } from "@/lib/api";
import { getErrorMessage, writeStorage } from "@/lib/helpers";

type Props = {
  baseUrl: string;
  onBaseUrlChange: (value: string) => void;
  onActivated: () => Promise<unknown> | void;
};

type SetupFormValues = {
  bot_token: string;
  openai_api_key: string;
  openai_base_url?: string;
  admin_api_token: string;
  run_mode: "polling" | "webhook";
  webhook_public_url?: string;
  ai_low_risk_model: string;
  ai_high_risk_model: string;
};

export function SetupWizardPage({ baseUrl, onBaseUrlChange, onActivated }: Props) {
  const { message } = AntApp.useApp();
  const api = useMemo(() => new ApiClient(baseUrl), [baseUrl]);
  const [step, setStep] = useState(0);
  const [authCode, setAuthCode] = useState("");
  const [setupToken, setSetupToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm<SetupFormValues>();

  const doAuth = async () => {
    if (!authCode.trim()) {
      message.warning("请输入首次启动口令");
      return;
    }
    setLoading(true);
    try {
      const out = await api.setupAuth(authCode.trim());
      setSetupToken(out.setup_token);
      setStep(1);
      message.success("口令验证成功");
    } catch (error) {
      message.error(`验证失败：${getErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const reissueCode = async () => {
    setLoading(true);
    try {
      const out = await api.setupReissueCode();
      setAuthCode(out.code);
      message.success(`已生成新口令（${out.expires_in_minutes} 分钟有效）`);
    } catch (error) {
      message.error(`重发失败：${getErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const saveAndActivate = async () => {
    if (!setupToken) {
      message.warning("请先完成口令验证");
      return;
    }
    try {
      const values = await form.validateFields();
      setLoading(true);
      await api.setupConfig(setupToken, values);
      await api.setupActivate(setupToken);
      writeStorage("bot_admin_token", values.admin_api_token);
      message.success("保存并激活成功");
      await onActivated();
    } catch (error) {
      message.error(`激活失败：${getErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="setup-page">
      <Card style={{ maxWidth: 980, margin: "32px auto" }}>
        <Space direction="vertical" size={20} style={{ width: "100%" }}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            首次配置向导
          </Typography.Title>
          <Typography.Text type="secondary">终端只负责安装与启动，业务配置全部在这里完成。</Typography.Text>
          <Steps
            current={step}
            items={[
              { title: "口令验证" },
              { title: "填写配置" },
              { title: "激活完成" },
            ]}
          />

          <Row gutter={16}>
            <Col xs={24} lg={10}>
              <Card type="inner" title="连接与验证">
                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                  <div>
                    <Typography.Text strong>后端地址</Typography.Text>
                    <Input value={baseUrl} onChange={(e) => onBaseUrlChange(e.target.value)} placeholder="http://127.0.0.1:10010" />
                  </div>
                  <div>
                    <Typography.Text strong>首次启动口令</Typography.Text>
                    <Input value={authCode} onChange={(e) => setAuthCode(e.target.value)} placeholder="终端输出的口令" />
                  </div>
                  <Space>
                    <Button type="primary" loading={loading} onClick={() => void doAuth()}>
                      验证口令
                    </Button>
                    <Button loading={loading} onClick={() => void reissueCode()}>
                      重新生成
                    </Button>
                  </Space>
                  {setupToken ? <Alert type="success" showIcon message="已验证成功，可填写配置并激活" /> : null}
                </Space>
              </Card>
            </Col>
            <Col xs={24} lg={14}>
              <Card type="inner" title="运行配置">
                <Form
                  form={form}
                  layout="vertical"
                  initialValues={{
                    run_mode: "polling",
                    ai_low_risk_model: "gpt-4.1-mini",
                    ai_high_risk_model: "gpt-5.2",
                  }}
                >
                  <Row gutter={12}>
                    <Col xs={24} md={12}>
                      <Form.Item label="BOT Token" name="bot_token" rules={[{ required: true, message: "必填" }]}>
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item label="管理 API Token" name="admin_api_token" rules={[{ required: true, message: "必填" }]}>
                        <Input.Password />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item label="OpenAI/兼容平台 Key" name="openai_api_key" rules={[{ required: true, message: "必填" }]}>
                        <Input.Password />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item label="兼容平台 Base URL" name="openai_base_url">
                        <Input placeholder="留空使用官方地址" />
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
                      <Form.Item label="低风险模型" name="ai_low_risk_model" rules={[{ required: true, message: "必填" }]}>
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item label="高风险模型" name="ai_high_risk_model" rules={[{ required: true, message: "必填" }]}>
                        <Input />
                      </Form.Item>
                    </Col>
                  </Row>
                </Form>
                <Button type="primary" loading={loading} onClick={() => void saveAndActivate()}>
                  保存并激活
                </Button>
              </Card>
            </Col>
          </Row>
        </Space>
      </Card>
    </div>
  );
}
