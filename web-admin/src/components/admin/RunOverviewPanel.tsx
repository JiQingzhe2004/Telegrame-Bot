import { Card, Col, Descriptions, Row, Space, Statistic, Tag } from "antd";
import { SafetyCertificateOutlined, TeamOutlined } from "@ant-design/icons";
import type { AdminDataBundle } from "@/components/admin/types";

type Props = {
  runtimeState: "setup" | "active";
  chatId: string;
  data: AdminDataBundle;
};

export function RunOverviewPanel({ runtimeState, chatId, data }: Props) {
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="运行状态" value={runtimeState.toUpperCase()} prefix={<SafetyCertificateOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="当前 Chat" value={chatId || "-"} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="成员池规模" value={data.members.length} prefix={<TeamOutlined />} />
          </Card>
        </Col>
      </Row>
      <Card title="群能力矩阵">
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label="群名">{data.overview?.chat.title ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="成员数">{data.overview?.member_count ?? "-"}</Descriptions.Item>
          {Object.entries(data.overview?.capabilities ?? {}).map(([name, ok]) => (
            <Descriptions.Item key={name} label={name}>
              <Tag color={ok ? "success" : "default"}>{ok ? "可用" : "不可用"}</Tag>
            </Descriptions.Item>
          ))}
        </Descriptions>
      </Card>
    </Space>
  );
}
