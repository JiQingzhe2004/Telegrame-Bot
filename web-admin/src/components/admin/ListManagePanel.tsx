import { useState } from "react";
import { Button, Card, Col, Input, Row, Space, Table, Tag } from "antd";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";

type Props = {
  data: AdminDataBundle;
  actions: AdminActions;
};

export function ListManagePanel({ data, actions }: Props) {
  const [white, setWhite] = useState("");
  const [black, setBlack] = useState("");

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={12}>
        <Card title="白名单">
          <Space.Compact style={{ width: "100%", marginBottom: 12 }}>
            <Input value={white} onChange={(e) => setWhite(e.target.value)} placeholder="@username 或 user_id" />
            <Button type="primary" onClick={() => void actions.addWhitelist(white)}>
              添加
            </Button>
          </Space.Compact>
          <Table
            rowKey="id"
            size="small"
            pagination={{ pageSize: 8 }}
            dataSource={data.whitelist}
            columns={[
              { title: "值", dataIndex: "value" },
              {
                title: "操作",
                width: 120,
                render: (_, row) => (
                  <Button size="small" onClick={() => void actions.removeWhitelist(row.value)}>
                    删除
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      </Col>
      <Col xs={24} xl={12}>
        <Card title="黑名单词">
          <Space.Compact style={{ width: "100%", marginBottom: 12 }}>
            <Input value={black} onChange={(e) => setBlack(e.target.value)} placeholder="违规词" />
            <Button danger type="primary" onClick={() => void actions.addBlacklist(black)}>
              添加
            </Button>
          </Space.Compact>
          <Table
            rowKey="id"
            size="small"
            pagination={{ pageSize: 8 }}
            dataSource={data.blacklist}
            columns={[
              {
                title: "值",
                dataIndex: "value",
                render: (value: string) => <Tag color="red">{value}</Tag>,
              },
              {
                title: "操作",
                width: 120,
                render: (_, row) => (
                  <Button size="small" onClick={() => void actions.removeBlacklist(row.value)}>
                    删除
                  </Button>
                ),
              },
            ]}
          />
        </Card>
      </Col>
    </Row>
  );
}
