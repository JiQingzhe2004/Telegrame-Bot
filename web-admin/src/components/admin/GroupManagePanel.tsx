import { useMemo, useState } from "react";
import { Button, Card, Col, Divider, Form, Input, Modal, Row, Space, Switch, Tabs, Tag, Typography } from "antd";
import { ProTable, type ProColumns } from "@ant-design/pro-components";
import type { AdminActionResult, ChatMemberBrief } from "@/lib/api";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { formatTime, translatePermission } from "@/lib/helpers";
import { UserLazySelect } from "@/components/admin/UserLazySelect";

type Props = {
  chatId: string;
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

  const capabilities = data.overview?.capabilities ?? {};
  const missingCapabilities = Object.entries(capabilities).filter(([, ok]) => !ok).map(([name]) => translatePermission(name));

  const withDangerConfirm = (content: string, action: () => Promise<void>) => {
    Modal.confirm({
      title: "二次确认",
      content,
      okType: "danger",
      onOk: action,
    });
  };

  const columns: ProColumns<ChatMemberBrief>[] = useMemo(
    () => [
      {
        title: "用户",
        dataIndex: "username",
        render: (_, row) => row.username || `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim() || "-",
      },
      { title: "User ID", dataIndex: "user_id", width: 170 },
      {
        title: "最后活跃",
        dataIndex: "last_message_at",
        width: 180,
        render: (_, row) => formatTime(row.last_message_at),
      },
      { title: "违规分", dataIndex: "strike_score", width: 90 },
      {
        title: "快捷操作",
        key: "actions",
        width: 280,
        render: (_, row) => (
          <Space>
            <Button size="small" onClick={() => setTargetUserId(String(row.user_id))}>
              选为目标
            </Button>
            <Button size="small" onClick={() => void actions.runAction(() => apiActions.mute(String(row.user_id), muteSeconds), "禁言成功")}>
              禁言
            </Button>
            <Button
              size="small"
              danger
              onClick={() =>
                withDangerConfirm(`确认封禁 chat=${chatId}, user=${row.user_id} ?`, () =>
                  actions.runAction(() => apiActions.ban(String(row.user_id)), "封禁成功"),
                )
              }
            >
              封禁
            </Button>
          </Space>
        ),
      },
    ],
    [actions, apiActions, chatId, muteSeconds],
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card
        title="操作目标"
        extra={
          <Space>
            <Tag color="blue">chat: {chatId}</Tag>
            <Tag color={targetUserId ? "green" : "default"}>{targetUserId ? `目标: ${targetUserId}` : "未选目标"}</Tag>
          </Space>
        }
      >
        <Row gutter={12}>
          <Col xs={24} md={8}>
            <Typography.Text type="secondary">目标用户 ID</Typography.Text>
            <UserLazySelect
              members={data.members}
              value={targetUserId}
              onChange={setTargetUserId}
            />
          </Col>
          <Col xs={24} md={8}>
            <Typography.Text type="secondary">禁言时长（秒）</Typography.Text>
            <Input type="number" value={muteSeconds} onChange={(e) => setMuteSeconds(Number(e.target.value))} />
          </Col>
          <Col xs={24} md={16} style={{ display: "flex", alignItems: "end" }}>
            <Space wrap>
              <Button onClick={() => void actions.runAction(() => apiActions.mute(targetUserId, muteSeconds), "禁言成功")}>禁言</Button>
              <Button onClick={() => void actions.runAction(() => apiActions.unmute(targetUserId), "解除禁言成功")}>解禁言</Button>
              <Button
                danger
                disabled={!targetUserId}
                onClick={() =>
                  withDangerConfirm(`确认封禁 chat=${chatId}, user=${targetUserId} ?`, () =>
                    actions.runAction(() => apiActions.ban(targetUserId), "封禁成功"),
                  )
                }
              >
                封禁
              </Button>
              <Button disabled={!targetUserId} onClick={() => void actions.runAction(() => apiActions.unban(targetUserId), "解封成功")}>
                解封
              </Button>
            </Space>
          </Col>
        </Row>
        <Divider style={{ margin: "14px 0" }} />
        {missingCapabilities.length > 0 ? (
          <Typography.Text style={{ color: "#d46b08", marginTop: 12, display: "inline-block" }}>
            当前缺少权限：{missingCapabilities.join("、")}。相关动作可能降级或失败。
          </Typography.Text>
        ) : null}
      </Card>

      <Card
        title="成员列表"
        extra={
          <Space>
            <Typography.Text type="secondary">5秒自动刷新</Typography.Text>
            <Switch checked={autoRefresh} onChange={setAutoRefresh} />
            <Button onClick={() => void requestMembersRefresh()}>立即刷新</Button>
          </Space>
        }
      >
        <Typography.Paragraph type="secondary">仅展示机器人实际收到过消息、或已被处置过的用户；这不是 Telegram 全量成员列表。</Typography.Paragraph>
        <ProTable<ChatMemberBrief>
          rowKey="user_id"
          columns={columns}
          dataSource={data.members}
          loading={data.isLoading}
          search={false}
          options={false}
          pagination={{ pageSize: 8 }}
          toolBarRender={() => [
            <Input.Search
              key="member-search"
              allowClear
              placeholder="搜索 user_id / 用户名 / 姓名"
              value={memberKeyword}
              onChange={(e) => setMemberKeyword(e.target.value)}
              onSearch={() => void requestMembersRefresh()}
              style={{ width: 360 }}
            />,
          ]}
        />
      </Card>

      <Tabs
        items={[
          {
            key: "messages",
            label: "消息管理",
            children: (
              <Card>
                <Form layout="vertical">
                  <Form.Item label="目标 Message ID">
                    <Input value={targetMessageId} onChange={(e) => setTargetMessageId(e.target.value)} />
                  </Form.Item>
                  <Space wrap>
                    <Button onClick={() => void actions.runAction(() => apiActions.deleteMessage(targetMessageId), "删除消息成功")}>删除消息</Button>
                    <Button onClick={() => void actions.runAction(() => apiActions.pinMessage(targetMessageId), "置顶成功")}>置顶消息</Button>
                    <Button onClick={() => void actions.runAction(() => apiActions.unpinMessage(), "取消置顶成功")}>取消置顶</Button>
                  </Space>
                </Form>
              </Card>
            ),
          },
          {
            key: "invite",
            label: "邀请链接",
            children: (
              <Card>
                <Form layout="vertical">
                  <Form.Item label="邀请链接名称（可选）">
                    <Input value={inviteName} onChange={(e) => setInviteName(e.target.value)} />
                  </Form.Item>
                  <Button onClick={() => void actions.runAction(() => apiActions.createInvite(inviteName), "创建邀请链接成功")}>创建邀请链接</Button>
                  <Form.Item label="待撤销 invite_link" style={{ marginTop: 16 }}>
                    <Input value={inviteLink} onChange={(e) => setInviteLink(e.target.value)} />
                  </Form.Item>
                  <Button onClick={() => void actions.runAction(() => apiActions.revokeInvite(inviteLink), "撤销邀请链接成功")}>撤销邀请链接</Button>
                </Form>
              </Card>
            ),
          },
          {
            key: "admins",
            label: "管理员管理",
            children: (
              <Card>
                <Form layout="vertical">
                  <Form.Item label="管理员用户 ID">
                    <UserLazySelect
                      members={data.members}
                      value={targetUserId}
                      onChange={setTargetUserId}
                    />
                  </Form.Item>
                  <Form.Item label="管理员头衔">
                    <Input value={adminTitle} onChange={(e) => setAdminTitle(e.target.value)} />
                  </Form.Item>
                  <Space wrap>
                    <Button
                      danger
                      disabled={!targetUserId}
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
                      disabled={!targetUserId}
                      onClick={() =>
                        withDangerConfirm(`确认降权 chat=${chatId}, user=${targetUserId} ?`, () =>
                          actions.runAction(() => apiActions.demote(targetUserId), "降权成功"),
                        )
                      }
                    >
                      移除管理员
                    </Button>
                    <Button disabled={!targetUserId} onClick={() => void actions.runAction(() => apiActions.setTitle(targetUserId, adminTitle), "设置头衔成功")}>
                      设置头衔
                    </Button>
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
            ),
          },
          {
            key: "profile",
            label: "群资料",
            children: (
              <Card>
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
            ),
          },
        ]}
      />
    </Space>
  );
}
