import { useState } from "react";
import { Button, Card, Col, Form, Input, Modal, Row, Space, Switch, Tag, Typography } from "antd";
import { ProTable, type ProColumns } from "@ant-design/pro-components";
import type { AdminActionResult, ChatMemberBrief } from "@/lib/api";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { formatTime } from "@/lib/helpers";

type Props = {
  chatId: string;
  adminToken: string;
  data: AdminDataBundle;
  actions: AdminActions;
  autoRefresh: boolean;
  setAutoRefresh: (value: boolean) => void;
  memberKeyword: string;
  setMemberKeyword: (value: string) => void;
  requestMembersRefresh: () => Promise<void>;
  apiActions: {
    mute: (userId: string, duration: number) => Promise<AdminActionResult>;
    unmute: (userId: string) => Promise<AdminActionResult>;
    ban: (userId: string) => Promise<AdminActionResult>;
    unban: (userId: string) => Promise<AdminActionResult>;
    deleteMessage: (messageId: string) => Promise<AdminActionResult>;
    pinMessage: (messageId: string) => Promise<AdminActionResult>;
    unpinMessage: () => Promise<AdminActionResult>;
    createInvite: (name: string) => Promise<AdminActionResult>;
    revokeInvite: (inviteLink: string) => Promise<AdminActionResult>;
    promote: (userId: string) => Promise<AdminActionResult>;
    demote: (userId: string) => Promise<AdminActionResult>;
    setTitle: (userId: string, title: string) => Promise<AdminActionResult>;
    updateProfile: (title: string, description: string) => Promise<AdminActionResult>;
  };
};

export function GroupManagePanel({
  chatId,
  adminToken,
  data,
  actions,
  autoRefresh,
  setAutoRefresh,
  memberKeyword,
  setMemberKeyword,
  requestMembersRefresh,
  apiActions,
}: Props) {
  const [targetUserId, setTargetUserId] = useState("");
  const [muteSeconds, setMuteSeconds] = useState(600);
  const [targetMessageId, setTargetMessageId] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteLink, setInviteLink] = useState("");
  const [adminTitle, setAdminTitle] = useState("");
  const [profileTitle, setProfileTitle] = useState(data.overview?.chat.title ?? "");
  const [profileDescription, setProfileDescription] = useState(data.overview?.chat.description ?? "");

  const columns: ProColumns<ChatMemberBrief>[] = [
    {
      title: "用户",
      dataIndex: "username",
      render: (_, row) => row.username || `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim() || "-",
    },
    { title: "User ID", dataIndex: "user_id", width: 180 },
    {
      title: "最后活跃",
      dataIndex: "last_message_at",
      render: (_, row) => formatTime(row.last_message_at),
      width: 180,
    },
    { title: "违规分", dataIndex: "strike_score", width: 90 },
    {
      title: "快捷操作",
      key: "action",
      width: 120,
      render: (_, row) => (
        <Button
          size="small"
          onClick={() => {
            setTargetUserId(String(row.user_id));
            actions.setTargetUser(String(row.user_id));
          }}
        >
          选中
        </Button>
      ),
    },
  ];

  const withDangerConfirm = (content: string, action: () => Promise<void>) => {
    Modal.confirm({
      title: "二次确认",
      content,
      okType: "danger",
      onOk: action,
    });
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card
        title="成员管理"
        extra={
          <Space>
            <Typography.Text type="secondary">实时刷新</Typography.Text>
            <Switch checked={autoRefresh} onChange={setAutoRefresh} />
            <Button onClick={() => void requestMembersRefresh()}>立即刷新</Button>
          </Space>
        }
      >
        <Typography.Paragraph type="secondary">
          成员数据来自已发言/已处置用户池，不是 Telegram 全量成员枚举。
        </Typography.Paragraph>
        <ProTable<ChatMemberBrief>
          rowKey="user_id"
          columns={columns}
          dataSource={data.members}
          search={false}
          options={false}
          loading={data.isLoading}
          pagination={{ pageSize: 8 }}
          toolBarRender={() => [
            <Input.Search
              key="search"
              allowClear
              placeholder="搜索 user_id/用户名/姓名"
              value={memberKeyword}
              onChange={(e) => setMemberKeyword(e.target.value)}
              onSearch={() => void requestMembersRefresh()}
              style={{ width: 320 }}
            />,
          ]}
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="成员处置">
            <Form layout="vertical">
              <Form.Item label="目标用户 ID">
                <Input value={targetUserId} onChange={(e) => setTargetUserId(e.target.value)} />
              </Form.Item>
              <Form.Item label="禁言时长（秒）">
                <Input type="number" value={muteSeconds} onChange={(e) => setMuteSeconds(Number(e.target.value))} />
              </Form.Item>
              <Space wrap>
                <Button onClick={() => void actions.runAction(() => apiActions.mute(targetUserId, muteSeconds), "禁言成功")}>禁言</Button>
                <Button onClick={() => void actions.runAction(() => apiActions.unmute(targetUserId), "解除禁言成功")}>解禁言</Button>
                <Button
                  danger
                  onClick={() =>
                    withDangerConfirm(`确认封禁 chat=${chatId}, user=${targetUserId} ?`, () =>
                      actions.runAction(() => apiActions.ban(targetUserId), "封禁成功"),
                    )
                  }
                >
                  封禁
                </Button>
                <Button onClick={() => void actions.runAction(() => apiActions.unban(targetUserId), "解封成功")}>解封</Button>
              </Space>
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="消息与邀请">
            <Form layout="vertical">
              <Form.Item label="目标 Message ID">
                <Input value={targetMessageId} onChange={(e) => setTargetMessageId(e.target.value)} />
              </Form.Item>
              <Space wrap>
                <Button onClick={() => void actions.runAction(() => apiActions.deleteMessage(targetMessageId), "删除成功")}>删除消息</Button>
                <Button onClick={() => void actions.runAction(() => apiActions.pinMessage(targetMessageId), "置顶成功")}>置顶消息</Button>
                <Button onClick={() => void actions.runAction(() => apiActions.unpinMessage(), "取消置顶成功")}>取消置顶</Button>
              </Space>
              <Form.Item label="邀请链接名称（可选）" style={{ marginTop: 16 }}>
                <Input value={inviteName} onChange={(e) => setInviteName(e.target.value)} />
              </Form.Item>
              <Space wrap>
                <Button onClick={() => void actions.runAction(() => apiActions.createInvite(inviteName), "已创建邀请链接")}>创建邀请链接</Button>
              </Space>
              <Form.Item label="待撤销 invite_link" style={{ marginTop: 16 }}>
                <Input value={inviteLink} onChange={(e) => setInviteLink(e.target.value)} />
              </Form.Item>
              <Button onClick={() => void actions.runAction(() => apiActions.revokeInvite(inviteLink), "已撤销邀请链接")}>撤销邀请链接</Button>
            </Form>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="管理员管理">
            <Form layout="vertical">
              <Form.Item label="管理员用户 ID">
                <Input value={targetUserId} onChange={(e) => setTargetUserId(e.target.value)} />
              </Form.Item>
              <Form.Item label="管理员头衔">
                <Input value={adminTitle} onChange={(e) => setAdminTitle(e.target.value)} />
              </Form.Item>
              <Space wrap>
                <Button
                  danger
                  onClick={() =>
                    withDangerConfirm(`确认提权 chat=${chatId}, user=${targetUserId} ?`, () =>
                      actions.runAction(() => apiActions.promote(targetUserId), "提权成功"),
                    )
                  }
                >
                  提升管理员
                </Button>
                <Button
                  danger
                  onClick={() =>
                    withDangerConfirm(`确认降权 chat=${chatId}, user=${targetUserId} ?`, () =>
                      actions.runAction(() => apiActions.demote(targetUserId), "降权成功"),
                    )
                  }
                >
                  移除管理员
                </Button>
                <Button onClick={() => void actions.runAction(() => apiActions.setTitle(targetUserId, adminTitle), "设置头衔成功")}>设置头衔</Button>
              </Space>
              <Space direction="vertical" size={8} style={{ width: "100%", marginTop: 16 }}>
                {data.overview?.administrators?.slice(0, 10).map((item) => (
                  <Card.Grid key={item.user_id} style={{ width: "100%", padding: 10 }}>
                    <Space>
                      <Tag>{item.status}</Tag>
                      <Typography.Text>{item.full_name}</Typography.Text>
                      <Typography.Text type="secondary">{item.user_id}</Typography.Text>
                    </Space>
                  </Card.Grid>
                ))}
              </Space>
            </Form>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="群资料">
            <Form layout="vertical">
              <Form.Item label="群标题">
                <Input value={profileTitle} onChange={(e) => setProfileTitle(e.target.value)} />
              </Form.Item>
              <Form.Item label="群描述">
                <Input.TextArea rows={4} value={profileDescription} onChange={(e) => setProfileDescription(e.target.value)} />
              </Form.Item>
              <Button type="primary" onClick={() => void actions.runAction(() => apiActions.updateProfile(profileTitle, profileDescription), "群资料更新成功")}>
                更新群资料
              </Button>
            </Form>
          </Card>
        </Col>
      </Row>
      <Typography.Text type="secondary">admin token 已载入: {adminToken ? "是" : "否"}</Typography.Text>
    </Space>
  );
}
