import { useMemo, useState } from "react";
import { AutoComplete, Button, Card, Col, Row, Space, Table, Tag } from "antd";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { UserLazySelect } from "@/components/admin/UserLazySelect";

type Props = {
  data: AdminDataBundle;
  actions: AdminActions;
};

export function ListManagePanel({ data, actions }: Props) {
  const [white, setWhite] = useState("");
  const [black, setBlack] = useState("");
  const blackOptions = useMemo(
    () => data.blacklist.map((item) => ({ value: item.value, label: item.value })),
    [data.blacklist],
  );

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={12}>
        <Card title="白名单">
          <Space.Compact style={{ width: "100%", marginBottom: 12 }}>
            <UserLazySelect
              members={data.members}
              value={white}
              onChange={setWhite}
              placeholder="@username 或 user_id（支持搜索）"
            />
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
            <AutoComplete
              options={blackOptions}
              value={black}
              style={{ width: "100%" }}
              onChange={(value) => setBlack(value)}
              placeholder="违规词（支持搜索）"
              filterOption={(inputValue, option) => (option?.label ?? "").toLowerCase().includes(inputValue.toLowerCase())}
            />
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
