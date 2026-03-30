import { Button, Card, Modal, Table, Tag } from "antd";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { formatTime } from "@/lib/helpers";

type Props = {
  data: AdminDataBundle;
  actions: AdminActions;
};

export function EnforcementPanel({ data, actions }: Props) {
  return (
    <Card title="处置记录">
      <Table
        rowKey="id"
        size="small"
        dataSource={data.enforcements}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: "ID", dataIndex: "id", width: 80, render: (id: number) => `#${id}` },
          { title: "用户", dataIndex: "user_id", width: 120 },
          {
            title: "动作",
            dataIndex: "action",
            width: 120,
            render: (action: string) => <Tag color={action === "ban" || action === "mute" ? "red" : "blue"}>{action}</Tag>,
          },
          { title: "原因", dataIndex: "reason", ellipsis: true },
          { title: "时间", dataIndex: "created_at", width: 180, render: (value: string) => formatTime(value) },
          {
            title: "回滚",
            width: 120,
            render: (_, row) => (
              <Button
                size="small"
                disabled={!["mute", "restrict"].includes(row.action)}
                onClick={() =>
                  Modal.confirm({
                    title: "确认回滚",
                    content: `确认回滚处置 #${row.id} 吗？`,
                    onOk: async () => actions.rollback(row.id),
                  })
                }
              >
                回滚
              </Button>
            ),
          },
        ]}
      />
    </Card>
  );
}
