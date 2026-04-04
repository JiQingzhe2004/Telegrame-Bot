import { useEffect, useState } from "react";
import { Crown, Link2, MessageSquareMore, Pin, Save, ShieldOff, ShieldPlus, Trash2, Undo2, UserCog } from "lucide-react";
import type { AdminActionResult } from "@/lib/api";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { UserLazySelect } from "@/components/admin/UserLazySelect";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type Props = {
  chatId: string;
  data: AdminDataBundle;
  actions: AdminActions;
  apiActions: {
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

export function GroupInfoPanel({ chatId, data, actions, apiActions }: Props) {
  const [targetUserId, setTargetUserId] = useState("");
  const [targetMessageId, setTargetMessageId] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteLink, setInviteLink] = useState("");
  const [adminTitle, setAdminTitle] = useState("");
  const [profileTitle, setProfileTitle] = useState(data.overview?.chat.title ?? "");
  const [profileDescription, setProfileDescription] = useState(data.overview?.chat.description ?? "");
  const [confirmAction, setConfirmAction] = useState<{
    title: string;
    description: string;
    action: () => Promise<void>;
  } | null>(null);

  useEffect(() => {
    setProfileTitle(data.overview?.chat.title ?? "");
    setProfileDescription(data.overview?.chat.description ?? "");
  }, [data.overview?.chat.description, data.overview?.chat.title]);

  return (
    <>
      <div className="flex flex-col gap-6">
        <Card className="admin-surface-card">
          <CardHeader>
            <CardTitle>群信息</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border bg-background/70 p-4 dark:bg-slate-900/70 dark:border-slate-700">
                <div className="text-xs text-muted-foreground">群标题</div>
                <div className="mt-1 font-medium">{data.overview?.chat.title ?? "-"}</div>
              </div>
              <div className="rounded-xl border bg-background/70 p-4 dark:bg-slate-900/70 dark:border-slate-700">
                <div className="text-xs text-muted-foreground">Chat ID</div>
                <div className="mt-1 font-medium">{chatId}</div>
              </div>
              <div className="rounded-xl border bg-background/70 p-4 dark:bg-slate-900/70 dark:border-slate-700">
                <div className="text-xs text-muted-foreground">管理员数量</div>
                <div className="mt-1 font-medium">{data.overview?.administrators?.length ?? 0}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Tabs defaultValue="profile" className="w-full">
          <TabsList className="grid h-auto grid-cols-2 gap-2 bg-transparent p-0 md:grid-cols-4">
            <TabsTrigger value="profile">群资料</TabsTrigger>
            <TabsTrigger value="admins">管理员管理</TabsTrigger>
            <TabsTrigger value="messages">消息管理</TabsTrigger>
            <TabsTrigger value="invite">邀请链接</TabsTrigger>
          </TabsList>

          <TabsContent value="profile">
            <Card className="admin-surface-card">
              <CardHeader>
                <CardTitle>群资料</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="space-y-2">
                  <Label>群标题</Label>
                  <Input value={profileTitle} onChange={(e) => setProfileTitle(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>群描述</Label>
                  <Textarea rows={4} value={profileDescription} onChange={(e) => setProfileDescription(e.target.value)} />
                </div>
                <Button className="w-fit" onClick={() => void actions.runAction(() => apiActions.updateProfile(profileTitle, profileDescription), "群资料更新成功")}>
                  <Save className="mr-2 h-4 w-4" />
                  更新群资料
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="admins">
            <Card className="admin-surface-card">
              <CardHeader>
                <CardTitle>管理员管理</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="space-y-2">
                  <Label>管理员用户 ID</Label>
                  <UserLazySelect members={data.members} value={targetUserId} onChange={setTargetUserId} />
                </div>
                <div className="space-y-2">
                  <Label>管理员头衔</Label>
                  <Input value={adminTitle} onChange={(e) => setAdminTitle(e.target.value)} />
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button
                    variant="destructive"
                    disabled={!targetUserId}
                    onClick={() =>
                      setConfirmAction({
                        title: "确认提升管理员",
                        description: `确认提权 chat=${chatId}, user=${targetUserId} ?`,
                        action: async () => {
                          await actions.runAction(() => apiActions.promote(targetUserId), "提权成功");
                        },
                      })
                    }
                  >
                    <ShieldPlus className="mr-2 h-4 w-4" />
                    提升管理员
                  </Button>
                  <Button
                    variant="destructive"
                    disabled={!targetUserId}
                    onClick={() =>
                      setConfirmAction({
                        title: "确认移除管理员",
                        description: `确认降权 chat=${chatId}, user=${targetUserId} ?`,
                        action: async () => {
                          await actions.runAction(() => apiActions.demote(targetUserId), "降权成功");
                        },
                      })
                    }
                  >
                    <ShieldOff className="mr-2 h-4 w-4" />
                    移除管理员
                  </Button>
                  <Button variant="outline" disabled={!targetUserId} onClick={() => void actions.runAction(() => apiActions.setTitle(targetUserId, adminTitle), "设置头衔成功")}>
                    <UserCog className="mr-2 h-4 w-4" />
                    设置头衔
                  </Button>
                </div>

                <div className="grid gap-3">
                  {data.overview?.administrators?.slice(0, 10).map((item) => (
                    <div key={item.user_id} className="rounded-xl border bg-background/70 p-4 dark:bg-slate-900/70 dark:border-slate-700">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{item.status}</Badge>
                        <span className="font-medium">{item.full_name}</span>
                        <span className="text-sm text-muted-foreground">{item.user_id}</span>
                        {item.custom_title ? <span className="text-sm text-muted-foreground">头衔: {item.custom_title}</span> : null}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="messages">
            <Card className="admin-surface-card">
              <CardHeader>
                <CardTitle>消息管理</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="space-y-2 rounded-xl border bg-background/60 p-4 dark:bg-slate-900/65 dark:border-slate-700">
                  <Label>目标 Message ID</Label>
                  <Input
                    value={targetMessageId}
                    onChange={(e) => setTargetMessageId(e.target.value)}
                    className="dark:border-slate-600 dark:bg-slate-950/80 dark:text-slate-100 dark:placeholder:text-slate-500"
                  />
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button
                    variant="destructive"
                    className="dark:bg-rose-500 dark:text-white dark:hover:bg-rose-400"
                    onClick={() => void actions.runAction(() => apiActions.deleteMessage(targetMessageId), "删除消息成功")}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    删除消息
                  </Button>
                  <Button
                    className="dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
                    onClick={() => void actions.runAction(() => apiActions.pinMessage(targetMessageId), "置顶成功")}
                  >
                    <Pin className="mr-2 h-4 w-4" />
                    置顶消息
                  </Button>
                  <Button
                    variant="outline"
                    className="dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                    onClick={() => void actions.runAction(() => apiActions.unpinMessage(), "取消置顶成功")}
                  >
                    <Undo2 className="mr-2 h-4 w-4" />
                    取消置顶
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="invite">
            <Card className="admin-surface-card">
              <CardHeader>
                <CardTitle>邀请链接</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="space-y-2">
                  <Label>邀请链接名称（可选）</Label>
                  <Input value={inviteName} onChange={(e) => setInviteName(e.target.value)} />
                </div>
                <Button className="w-fit" onClick={() => void actions.runAction(() => apiActions.createInvite(inviteName), "创建邀请链接成功")}>
                  <Link2 className="mr-2 h-4 w-4" />
                  创建邀请链接
                </Button>
                <div className="space-y-2">
                  <Label>待撤销 invite_link</Label>
                  <Input value={inviteLink} onChange={(e) => setInviteLink(e.target.value)} />
                </div>
                <Button variant="outline" className="w-fit" onClick={() => void actions.runAction(() => apiActions.revokeInvite(inviteLink), "撤销邀请链接成功")}>
                  <MessageSquareMore className="mr-2 h-4 w-4" />
                  撤销邀请链接
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      <Dialog open={confirmAction !== null} onOpenChange={(open) => !open && setConfirmAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{confirmAction?.title ?? "二次确认"}</DialogTitle>
            <DialogDescription>{confirmAction?.description ?? ""}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmAction(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (!confirmAction) return;
                await confirmAction.action();
                setConfirmAction(null);
              }}
            >
              <Crown className="mr-2 h-4 w-4" />
              确认
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
