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
          { title: "置信度", dataIndex: "confidence", width: 100, render: (v: number) => Number(v).toFixed(2) },
          { title: "时间", dataIndex: "created_at", width: 180, render: (value: string) => formatTime(value) },
        ]}
      />
    </Card>
  );
}
