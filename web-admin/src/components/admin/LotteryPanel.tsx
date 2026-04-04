import { useEffect, useMemo, useState } from "react";
import { Gift, Plus, RefreshCw, Trash2, Trophy } from "lucide-react";
import type { LotteryDetail, LotteryEntry, LotteryPayload } from "@/lib/api";
import type { AdminDataBundle } from "@/components/admin/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

type Props = {
  data: AdminDataBundle;
  onRefresh: () => Promise<void>;
  onCreateLottery: (payload: LotteryPayload) => Promise<void>;
  onUpdateLottery: (lotteryId: number, payload: LotteryPayload) => Promise<void>;
  onCancelLottery: (lotteryId: number) => Promise<void>;
  onDrawLottery: (lotteryId: number) => Promise<void>;
  onLoadEntries: (lotteryId: number) => Promise<void>;
};

const emptyPayload: LotteryPayload = {
  title: "",
  description: "",
  entry_mode: "free",
  points_cost: 0,
  points_threshold: 0,
  allow_multiple_entries: false,
  max_entries_per_user: 1,
  show_participants: true,
  starts_at: "",
  entry_deadline_at: "",
  draw_at: "",
  prizes: [
    { title: "一等奖", winner_count: 1, sort_order: 0 },
  ],
};

function toDateTimeLocal(value?: string | null) {
  if (!value) return "";
  return value.slice(0, 16);
}

export function LotteryPanel({
  data,
  onRefresh,
  onCreateLottery,
  onUpdateLottery,
  onCancelLottery,
  onDrawLottery,
  onLoadEntries,
}: Props) {
  const [selectedLotteryId, setSelectedLotteryId] = useState<number | null>(null);
  const [formState, setFormState] = useState<LotteryPayload>(emptyPayload);

  useEffect(() => {
    if (!selectedLotteryId && data.lotteries.length > 0) {
      setSelectedLotteryId(data.lotteries[0].id);
    }
  }, [data.lotteries, selectedLotteryId]);

  const selectedLottery = useMemo(
    () => data.lotteries.find((item) => item.id === selectedLotteryId) ?? null,
    [data.lotteries, selectedLotteryId],
  );

  useEffect(() => {
    if (!selectedLottery) {
      setFormState(emptyPayload);
      return;
    }
    setFormState({
      title: selectedLottery.title,
      description: selectedLottery.description ?? "",
      entry_mode: selectedLottery.entry_mode,
      points_cost: selectedLottery.points_cost,
      points_threshold: selectedLottery.points_threshold,
      allow_multiple_entries: selectedLottery.allow_multiple_entries,
      max_entries_per_user: selectedLottery.max_entries_per_user,
      show_participants: selectedLottery.show_participants,
      starts_at: toDateTimeLocal(selectedLottery.starts_at),
      entry_deadline_at: toDateTimeLocal(selectedLottery.entry_deadline_at),
      draw_at: toDateTimeLocal(selectedLottery.draw_at),
      prizes: selectedLottery.prizes.map((prize, index) => ({
        title: prize.title,
        winner_count: prize.winner_count,
        sort_order: prize.sort_order ?? index,
      })),
    });
  }, [selectedLottery]);

  const selectedEntries = selectedLotteryId
    ? data.lotteryEntries.filter((item) => item.lottery_id === selectedLotteryId)
    : [];

  return (
    <div className="flex flex-col gap-6">
      <Card className="admin-surface-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>抽奖活动管理</CardTitle>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void onRefresh()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setSelectedLotteryId(null);
                setFormState(emptyPayload);
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              新建活动
            </Button>
          </div>
        </CardHeader>
        <CardContent className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <div className="space-y-4 rounded-xl border bg-muted/20 p-4">
            <div className="space-y-2">
              <Label>活动标题</Label>
              <Input value={formState.title} onChange={(e) => setFormState((prev) => ({ ...prev, title: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>活动说明</Label>
              <Textarea rows={4} value={formState.description} onChange={(e) => setFormState((prev) => ({ ...prev, description: e.target.value }))} />
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>参与模式</Label>
                <Select value={formState.entry_mode} onValueChange={(value: LotteryPayload["entry_mode"]) => setFormState((prev) => ({ ...prev, entry_mode: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="free">免费参与</SelectItem>
                    <SelectItem value="consume_points">扣积分参与</SelectItem>
                    <SelectItem value="balance_threshold">积分门槛</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>单次消耗积分</Label>
                <Input type="number" value={formState.points_cost} onChange={(e) => setFormState((prev) => ({ ...prev, points_cost: Number(e.target.value) }))} />
              </div>
              <div className="space-y-2">
                <Label>积分门槛</Label>
                <Input type="number" value={formState.points_threshold} onChange={(e) => setFormState((prev) => ({ ...prev, points_threshold: Number(e.target.value) }))} />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>开始时间</Label>
                <Input type="datetime-local" value={formState.starts_at} onChange={(e) => setFormState((prev) => ({ ...prev, starts_at: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>报名截止</Label>
                <Input type="datetime-local" value={formState.entry_deadline_at} onChange={(e) => setFormState((prev) => ({ ...prev, entry_deadline_at: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>开奖时间</Label>
                <Input type="datetime-local" value={formState.draw_at} onChange={(e) => setFormState((prev) => ({ ...prev, draw_at: e.target.value }))} />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex items-center justify-between rounded-xl border bg-background/70 p-4">
                <div>
                  <Label className="text-sm font-semibold">允许多次参与</Label>
                  <p className="text-xs text-muted-foreground">关闭后每人仅可报名一次。</p>
                </div>
                <Switch checked={formState.allow_multiple_entries} onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, allow_multiple_entries: checked }))} />
              </div>
              <div className="flex items-center justify-between rounded-xl border bg-background/70 p-4">
                <div>
                  <Label className="text-sm font-semibold">展示参与统计</Label>
                  <p className="text-xs text-muted-foreground">群内活动文案显示当前参与人数和份数。</p>
                </div>
                <Switch checked={formState.show_participants} onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, show_participants: checked }))} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>单用户最大参与次数</Label>
              <Input type="number" value={formState.max_entries_per_user} onChange={(e) => setFormState((prev) => ({ ...prev, max_entries_per_user: Number(e.target.value) }))} />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>奖项层级</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setFormState((prev) => ({
                      ...prev,
                      prizes: [
                        ...prev.prizes,
                        { title: `奖项 ${prev.prizes.length + 1}`, winner_count: 1, sort_order: prev.prizes.length },
                      ],
                    }))
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  新增奖项
                </Button>
              </div>
              {formState.prizes.map((prize, index) => (
                <div key={`${prize.title}-${index}`} className="grid gap-3 rounded-xl border bg-background/70 p-4 md:grid-cols-[1fr_120px_80px]">
                  <Input
                    value={prize.title}
                    onChange={(e) =>
                      setFormState((prev) => ({
                        ...prev,
                        prizes: prev.prizes.map((item, i) => (i === index ? { ...item, title: e.target.value } : item)),
                      }))
                    }
                    placeholder="奖项名称"
                  />
                  <Input
                    type="number"
                    value={prize.winner_count}
                    onChange={(e) =>
                      setFormState((prev) => ({
                        ...prev,
                        prizes: prev.prizes.map((item, i) => (i === index ? { ...item, winner_count: Number(e.target.value) } : item)),
                      }))
                    }
                    placeholder="名额"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    disabled={formState.prizes.length <= 1}
                    onClick={() =>
                      setFormState((prev) => ({
                        ...prev,
                        prizes: prev.prizes.filter((_, i) => i !== index).map((item, i) => ({ ...item, sort_order: i })),
                      }))
                    }
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void onCreateLottery(formState)}>
                <Gift className="mr-2 h-4 w-4" />
                发布新活动
              </Button>
              {selectedLottery ? (
                <>
                  <Button variant="outline" onClick={() => void onUpdateLottery(selectedLottery.id, formState)}>
                    保存当前活动
                  </Button>
                  <Button variant="destructive" onClick={() => void onCancelLottery(selectedLottery.id)}>
                    取消活动
                  </Button>
                  <Button variant="outline" onClick={() => void onDrawLottery(selectedLottery.id)}>
                    <Trophy className="mr-2 h-4 w-4" />
                    立即开奖
                  </Button>
                </>
              ) : null}
            </div>
          </div>

          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="mb-3 text-sm font-semibold">活动列表</div>
            <div className="space-y-3">
              {data.lotteries.length === 0 ? (
                <div className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">还没有抽奖活动</div>
              ) : (
                data.lotteries.map((lottery) => (
                  <button
                    key={lottery.id}
                    type="button"
                    className={`w-full rounded-xl border p-4 text-left ${selectedLotteryId === lottery.id ? "border-primary bg-background" : "bg-background/70"}`}
                    onClick={() => {
                      setSelectedLotteryId(lottery.id);
                      void onLoadEntries(lottery.id);
                    }}
                  >
                    <div className="font-medium">{lottery.title}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      状态：{lottery.status} | 参与人数：{lottery.stats.unique_users} | 已扣积分：{lottery.stats.total_points_spent}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">开奖时间：{lottery.draw_at}</div>
                  </button>
                ))
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="admin-surface-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>报名记录</CardTitle>
          {selectedLottery ? (
            <Button variant="outline" onClick={() => void onLoadEntries(selectedLottery.id)}>
              刷新记录
            </Button>
          ) : null}
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用户</TableHead>
                <TableHead>参与份数</TableHead>
                <TableHead>消耗积分</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {selectedEntries.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">当前活动还没有报名记录</TableCell>
                </TableRow>
              ) : (
                selectedEntries.map((entry: LotteryEntry) => (
                  <TableRow key={entry.id}>
                    <TableCell>{`${entry.first_name ?? ""} ${entry.last_name ?? ""}`.trim() || entry.username || entry.user_id}</TableCell>
                    <TableCell>{entry.entry_count}</TableCell>
                    <TableCell>{entry.points_spent}</TableCell>
                    <TableCell>{entry.source}</TableCell>
                    <TableCell>{entry.status}</TableCell>
                    <TableCell>{entry.created_at}</TableCell>
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
