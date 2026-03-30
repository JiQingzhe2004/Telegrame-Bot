import { Card, Empty, List, Tag, Typography } from "antd";
import type { AdminDataBundle } from "@/components/admin/types";
import { formatTime } from "@/lib/helpers";

type Props = {
  data: AdminDataBundle;
};

export function AppealsPanel({ data }: Props) {
  return (
    <Card title="申诉与回滚">
      <List
        dataSource={data.appeals}
        locale={{ emptyText: <Empty description="暂无申诉记录" /> }}
        renderItem={(item) => (
          <List.Item>
            <List.Item.Meta
              title={
                <>
                  <Tag>#{item.id}</Tag>
                  <Typography.Text type="secondary">user: {item.user_id}</Typography.Text>
                </>
              }
              description={
                <>
                  <Typography.Paragraph style={{ marginBottom: 4 }}>{item.message}</Typography.Paragraph>
                  <Typography.Text type="secondary">{formatTime(item.created_at)}</Typography.Text>
                </>
              }
            />
          </List.Item>
        )}
      />
    </Card>
  );
}
