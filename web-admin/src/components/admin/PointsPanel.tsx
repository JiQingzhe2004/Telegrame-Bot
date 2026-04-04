import { useEffect, useState } from "react";
import { Coins, Plus, Search, Wallet } from "lucide-react";
import type { ChatPointsConfig, PointsBalance, PointsLedgerEntry } from "@/lib/api";
import { UserLazySelect } from "@/components/admin/UserLazySelect";
import type { AdminDataBundle } from "@/components/admin/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Props = {
  data: AdminDataBundle;
  balance?: PointsBalance;
  queriedUserId: string;
  setQueriedUserId: (value: string) => void;
  onRefresh: () => Promise<void>;
  onQueryBalance: () => Promise<void>;
  onSaveConfig: (payload: Partial<ChatPointsConfig>) => Promise<void>;
  onAdjustPoints: (payload: { user_id: string; amount: number; reason?: string }) => Promise<void>;
};

export function PointsPanel({
  data,
  balance,
  queriedUserId,
  setQueriedUserId,
  onRefresh,
  onQueryBalance,
  onSaveConfig,
  onAdjustPoints,
}: Props) {
  const [configState, setConfigState] = useState<ChatPointsConfig>({
    points_enabled: true,
    points_message_reward: 1,
    points_message_cooldown_seconds: 60,
    points_daily_cap: 20,
    points_transfer_enabled: true,
    points_transfer_min_amount: 1,
  });
  const [adjustUserId, setAdjustUserId] = useState("");
  const [adjustAmount, setAdjustAmount] = useState("1");
  const [adjustReason, setAdjustReason] = useState("");

  useEffect(() => {
    if (data.pointsConfig) {
      setConfigState(data.pointsConfig);
    }
  }, [data.pointsConfig]);

  return (
    <div className="flex flex-col gap-6">
      <Card className="admin-surface-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>积分规则</CardTitle>
          </div>
          <Button variant="outline" onClick={() => void onRefresh()}>
            刷新
          </Button>
        </CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-2">
          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <Label className="text-sm font-semibold">积分功能开关</Label>
                <p className="text-xs text-muted-foreground">控制本群积分系统是否启用。</p>
              </div>
              <Switch
                checked={configState.points_enabled}
                onCheckedChange={(checked) => setConfigState((prev) => ({ ...prev, points_enabled: checked }))}
              />
            </div>
          </div>
          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <Label className="text-sm font-semibold">转账开关</Label>
                <p className="text-xs text-muted-foreground">控制用户间是否允许转账。</p>
              </div>
              <Switch
                checked={configState.points_transfer_enabled}
                onCheckedChange={(checked) => setConfigState((prev) => ({ ...prev, points_transfer_enabled: checked }))}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>发言奖励</Label>
            <Input type="number" value={configState.points_message_reward} onChange={(e) => setConfigState((prev) => ({ ...prev, points_message_reward: Number(e.target.value) }))} />
          </div>
          <div className="space-y-2">
            <Label>发言冷却秒数</Label>
            <Input type="number" value={configState.points_message_cooldown_seconds} onChange={(e) => setConfigState((prev) => ({ ...prev, points_message_cooldown_seconds: Number(e.target.value) }))} />
          </div>
          <div className="space-y-2">
            <Label>每日上限</Label>
            <Input type="number" value={configState.points_daily_cap} onChange={(e) => setConfigState((prev) => ({ ...prev, points_daily_cap: Number(e.target.value) }))} />
          </div>
          <div className="space-y-2">
            <Label>最小转账额</Label>
            <Input type="number" value={configState.points_transfer_min_amount} onChange={(e) => setConfigState((prev) => ({ ...prev, points_transfer_min_amount: Number(e.target.value) }))} />
          </div>
          <div className="md:col-span-2">
            <Button onClick={() => void onSaveConfig(configState)}>
              <Coins className="mr-2 h-4 w-4" />
              保存积分配置
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="admin-surface-card">
        <CardHeader>
          <CardTitle>用户查看方式</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          用户在群里执行 <code>/points</code>，或者点击“查看我的积分”按钮时，都不会公开显示余额，机器人会改为私聊发送积分详情。
          用户如果还没和机器人建立私聊，需要先打开机器人对话并发送一次 <code>/start</code>。
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="admin-surface-card">
          <CardHeader>
            <CardTitle>余额查询</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="flex-1">
                <UserLazySelect members={data.members} value={queriedUserId} onChange={setQueriedUserId} placeholder="选择或输入用户 ID" />
              </div>
              <Button onClick={() => void onQueryBalance()}>
                <Search className="mr-2 h-4 w-4" />
                查询
              </Button>
            </div>
            {balance ? (
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border bg-background/70 p-4">
                  <div className="text-xs text-muted-foreground">当前余额</div>
                  <div className="mt-1 text-xl font-semibold">{balance.balance}</div>
                </div>
                <div className="rounded-xl border bg-background/70 p-4">
                  <div className="text-xs text-muted-foreground">累计收入</div>
                  <div className="mt-1 text-xl font-semibold">{balance.total_earned}</div>
                </div>
                <div className="rounded-xl border bg-background/70 p-4">
                  <div className="text-xs text-muted-foreground">累计支出</div>
                  <div className="mt-1 text-xl font-semibold">{balance.total_spent}</div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
                选择成员后可查询余额
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="admin-surface-card">
          <CardHeader>
            <CardTitle>手动加减分</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <UserLazySelect members={data.members} value={adjustUserId} onChange={setAdjustUserId} placeholder="选择或输入用户 ID" />
            <Input type="number" value={adjustAmount} onChange={(e) => setAdjustAmount(e.target.value)} placeholder="正数加分，负数扣分" />
            <Input value={adjustReason} onChange={(e) => setAdjustReason(e.target.value)} placeholder="原因（可空）" />
            <Button onClick={() => void onAdjustPoints({ user_id: adjustUserId, amount: Number(adjustAmount), reason: adjustReason.trim() || undefined })}>
              <Plus className="mr-2 h-4 w-4" />
              执行调整
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card className="admin-surface-card">
        <CardHeader>
          <CardTitle>积分排行榜</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用户</TableHead>
                <TableHead>余额</TableHead>
                <TableHead>累计收入</TableHead>
                <TableHead>累计支出</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.pointsLeaderboard.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">暂无积分记录</TableCell>
                </TableRow>
              ) : (
                data.pointsLeaderboard.map((row) => {
                  const displayName = `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim() || row.username || row.user_id;
                  return (
                    <TableRow key={row.user_id}>
                      <TableCell>{displayName}</TableCell>
                      <TableCell>{row.balance}</TableCell>
                      <TableCell>{row.total_earned}</TableCell>
                      <TableCell>{row.total_spent}</TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="admin-surface-card">
        <CardHeader>
          <CardTitle>最近流水</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用户</TableHead>
                <TableHead>变动</TableHead>
                <TableHead>余额</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>原因</TableHead>
                <TableHead>时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.pointsLedger.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">暂无积分流水</TableCell>
                </TableRow>
              ) : (
                data.pointsLedger.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.user_id}</TableCell>
                    <TableCell>{row.change_amount}</TableCell>
                    <TableCell>{row.balance_after}</TableCell>
                    <TableCell>{row.event_type}</TableCell>
                    <TableCell>{row.reason || "-"}</TableCell>
                    <TableCell>{row.created_at}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
