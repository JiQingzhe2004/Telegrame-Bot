import { useMemo, useState } from "react";
import { Alert, App as AntApp, Button, Card, Col, Form, Input, InputNumber, Popconfirm, Row, Select, Space, Table, Tag, Typography } from "antd";
import type { VerificationQuestion } from "@/lib/api";
import { formatTime } from "@/lib/helpers";

type QuestionPayload = {
  scope: "chat" | "global";
  question: string;
  options: string[];
  answer_index: number;
};

type Props = {
  chatId?: string;
  loading: boolean;
  generating: boolean;
  questionType: "button" | "quiz";
  questions: VerificationQuestion[];
  onCreate: (payload: QuestionPayload) => Promise<void>;
  onUpdate: (questionId: number, payload: QuestionPayload) => Promise<void>;
  onDelete: (questionId: number) => Promise<void>;
  onGenerate: (payload: { scope: "chat" | "global"; count: number; topic_hint?: string }) => Promise<void>;
};

type FormValues = {
  scope: "chat" | "global";
  question: string;
  option_0: string;
  option_1: string;
  option_2?: string;
  option_3?: string;
  answer_original_index?: number;
};

const OPTION_FIELDS = ["option_0", "option_1", "option_2", "option_3"] as const;

function toFormValues(item: VerificationQuestion): FormValues {
  return {
    scope: item.scope,
    question: item.question,
    option_0: item.options[0] ?? "",
    option_1: item.options[1] ?? "",
    option_2: item.options[2] ?? "",
    option_3: item.options[3] ?? "",
    answer_original_index: item.answer_index,
  };
}

export function VerificationQuestionPanel({
  chatId,
  loading,
  generating,
  questionType,
  questions,
  onCreate,
  onUpdate,
  onDelete,
  onGenerate,
}: Props) {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm<FormValues>();
  const [generateForm] = Form.useForm<{ scope: "chat" | "global"; count: number; topic_hint?: string }>();
  const [editingId, setEditingId] = useState<number | null>(null);
  const watched = Form.useWatch([], form) as Partial<FormValues> | undefined;

  const filledOptions = useMemo(
    () =>
      OPTION_FIELDS.map((field, index) => ({
        originalIndex: index,
        text: String(watched?.[field] ?? "").trim(),
      })).filter((item) => item.text),
    [watched],
  );

  const answerChoices = filledOptions.map((item, index) => ({
    label: `${String.fromCharCode(65 + index)}. ${item.text}`,
    value: item.originalIndex,
  }));

  const resetForm = () => {
    setEditingId(null);
    form.setFieldsValue({
      scope: "chat",
      question: "",
      option_0: "",
      option_1: "",
      option_2: "",
      option_3: "",
      answer_original_index: undefined,
    });
  };

  const buildPayload = async (): Promise<QuestionPayload> => {
    const values = await form.validateFields();
    const optionPairs = OPTION_FIELDS.map((field, originalIndex) => ({
      originalIndex,
      text: String(values[field] ?? "").trim(),
    })).filter((item) => item.text);
    if (optionPairs.length < 2 || optionPairs.length > 4) {
      throw new Error("请填写 2 到 4 个选项");
    }
    const answerOriginalIndex = Number(values.answer_original_index);
    const answerIndex = optionPairs.findIndex((item) => item.originalIndex === answerOriginalIndex);
    if (answerIndex < 0) {
      throw new Error("请选择正确答案");
    }
    return {
      scope: values.scope,
      question: values.question.trim(),
      options: optionPairs.map((item) => item.text),
      answer_index: answerIndex,
    };
  };

  const handleSubmit = async () => {
    try {
      const payload = await buildPayload();
      if (editingId === null) {
        await onCreate(payload);
      } else {
        await onUpdate(editingId, payload);
      }
      resetForm();
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    }
  };

  const columns = [
    {
      title: "范围",
      dataIndex: "scope",
      width: 90,
      render: (_: unknown, row: VerificationQuestion) =>
        row.scope === "global" ? <Tag color="gold">全局</Tag> : <Tag color="blue">当前群</Tag>,
    },
    {
      title: "题目",
      dataIndex: "question",
      ellipsis: true,
    },
    {
      title: "选项",
      dataIndex: "options",
      render: (_: unknown, row: VerificationQuestion) => row.options.join(" / "),
    },
    {
      title: "正确答案",
      dataIndex: "answer_text",
      width: 220,
      render: (_: unknown, row: VerificationQuestion) => row.answer_text ?? "-",
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 180,
      render: (_: unknown, row: VerificationQuestion) => formatTime(row.created_at),
    },
    {
      title: "操作",
      key: "actions",
      width: 150,
      render: (_: unknown, row: VerificationQuestion) => (
        <Space>
          <Button
            size="small"
            onClick={() => {
              setEditingId(row.id);
              form.setFieldsValue(toFormValues(row));
            }}
          >
            编辑
          </Button>
          <Popconfirm title="确认删除这道验证题？" onConfirm={() => onDelete(row.id)}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      size="small"
      title="入群验证题库"
      extra={
        <Space>
          {chatId ? <Tag color="blue">Chat {chatId}</Tag> : null}
          <Tag color={questionType === "quiz" ? "processing" : "default"}>{questionType === "quiz" ? "当前使用题库模式" : "当前使用按钮模式"}</Tag>
        </Space>
      }
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          message="切到 quiz 后，会从当前群题库随机出题；当前群没有题时，会回退到全局题库；全都没有时再降级成按钮验证。"
        />
        {questionType === "quiz" && questions.length === 0 ? (
          <Alert type="warning" showIcon message="当前题库为空，quiz 模式下会自动降级成按钮验证。" />
        ) : null}
        <Card size="small" title="AI 生成题库">
          <Form
            form={generateForm}
            layout="vertical"
            initialValues={{
              scope: "chat",
              count: 3,
              topic_hint: "",
            }}
          >
            <Row gutter={12}>
              <Col xs={24} md={8}>
                <Form.Item label="生成范围" name="scope" rules={[{ required: true, message: "必选" }]}>
                  <Select
                    options={[
                      { label: "当前群", value: "chat" },
                      { label: "全局题库", value: "global" },
                    ]}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} md={8}>
                <Form.Item label="生成数量" name="count" rules={[{ required: true, message: "必填" }]}>
                  <InputNumber min={1} max={5} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
              <Col xs={24} md={8}>
                <Form.Item label="话题提示（可空）" name="topic_hint">
                  <Input placeholder="例如：群规、技术交流、礼貌发言" />
                </Form.Item>
              </Col>
              <Col xs={24}>
                <Button
                  type="primary"
                  loading={generating}
                  disabled={!chatId}
                  onClick={async () => {
                    try {
                      const values = await generateForm.validateFields();
                      await onGenerate({
                        scope: values.scope,
                        count: Number(values.count),
                        topic_hint: values.topic_hint?.trim() || undefined,
                      });
                    } catch (error) {
                      if (error instanceof Error) {
                        message.error(error.message);
                      }
                    }
                  }}
                >
                  使用当前 AI 配置生成题目
                </Button>
              </Col>
            </Row>
          </Form>
        </Card>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            scope: "chat",
            option_0: "",
            option_1: "",
            option_2: "",
            option_3: "",
          }}
        >
          <Row gutter={12}>
            <Col xs={24} md={8}>
              <Form.Item label="题目范围" name="scope" rules={[{ required: true, message: "必选" }]}>
                <Select
                  options={[
                    { label: "当前群", value: "chat" },
                    { label: "全局题库", value: "global" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={16}>
              <Form.Item label="题目" name="question" rules={[{ required: true, message: "必填" }]}>
                <Input placeholder="例如：本群讨论时应优先做什么？" />
              </Form.Item>
            </Col>
            {OPTION_FIELDS.map((field, index) => (
              <Col xs={24} md={12} key={field}>
                <Form.Item
                  label={`选项 ${String.fromCharCode(65 + index)}`}
                  name={field}
                  rules={index < 2 ? [{ required: true, message: "前两个选项必填" }] : undefined}
                >
                  <Input placeholder={`请输入选项 ${String.fromCharCode(65 + index)}`} />
                </Form.Item>
              </Col>
            ))}
            <Col xs={24} md={12}>
              <Form.Item label="正确答案" name="answer_original_index" rules={[{ required: true, message: "必选" }]}>
                <Select placeholder="先填写选项再选择" options={answerChoices} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12} style={{ display: "flex", alignItems: "end" }}>
              <Space wrap>
                <Button type="primary" loading={loading} disabled={!chatId} onClick={() => void handleSubmit()}>
                  {editingId === null ? "新增题目" : "保存修改"}
                </Button>
                <Button onClick={resetForm}>清空</Button>
              </Space>
            </Col>
          </Row>
        </Form>
        <Typography.Text type="secondary">
          前两个选项必填，最多支持 4 个选项。前端会直接显示题目、全部选项和正确答案。
        </Typography.Text>
        <Table<VerificationQuestion>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={questions}
          pagination={{ pageSize: 6 }}
          locale={{ emptyText: "当前还没有验证题" }}
        />
      </Space>
    </Card>
  );
}
