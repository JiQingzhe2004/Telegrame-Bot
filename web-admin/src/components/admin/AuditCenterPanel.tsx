import { Card, Table, Tag } from "antd";
import type { AdminDataBundle } from "@/components/admin/types";
import { formatTime } from "@/lib/helpers";

type Props = {
  data: AdminDataBundle;
};

export function AuditCenterPanel({ data }: Props) {
  return (
    <Card title="审计中心">
      <Table
        rowKey="id"
        size="small"
        dataSource={data.audits}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: "ID", dataIndex: "id", width: 80, render: (id: number) => `#${id}` },
          { title: "用户", dataIndex: "user_id", width: 120 },
          {
            title: "AI 状态",
            dataIndex: "ai_status",
            width: 120,
            render: (status: "skipped" | "success" | "failed") => {
              if (status === "success") return <Tag color="success">成功</Tag>;
              if (status === "failed") return <Tag color="error">失败</Tag>;
              return <Tag>跳过</Tag>;
            },
          },
          {
            title: "等级",
            dataIndex: "final_level",
            width: 110,
            render: (level: number) => {
              if (level >= 3) return <Tag color="red">L3</Tag>;
              if (level === 2) return <Tag color="orange">L2</Tag>;
              if (level === 1) return <Tag>L1</Tag>;
              return <Tag color="default">L0</Tag>;
            },
          },
          { title: "规则/AI", dataIndex: "rule_hit", ellipsis: true },
          {
            title: "AI 错误",
            dataIndex: "ai_error",
            ellipsis: true,
            render: (value: string | null) => value || "-",
          },
          { title: "置信度", dataIndex: "confidence", width: 100, render: (v: number) => Number(v).toFixed(2) },
          { title: "时间", dataIndex: "created_at", width: 180, render: (value: string) => formatTime(value) },
        ]}
      />
    </Card>
  );
}
