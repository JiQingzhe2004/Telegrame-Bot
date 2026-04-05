import { useEffect, useMemo, useState } from "react";
import { Gift, Plus, RefreshCw, Trash2, Trophy } from "lucide-react";
import { toast } from "sonner";
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
import { DateTimePicker } from "@/components/ui/date-time-picker";

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
  prize_source: "personal_points",
  starts_at: "",
  entry_deadline_at: "",
  draw_at: "",
  prizes: [
    { title: "一等奖", winner_count: 1, bonus_points: 0, sort_order: 0 },
  ],
};

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
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [formState, setFormState] = useState<LotteryPayload>(emptyPayload);

  useEffect(() => {
    if (!selectedLotteryId && !isCreatingNew && data.lotteries.length > 0) {
      setSelectedLotteryId(data.lotteries[0].id);
    }
  }, [data.lotteries, isCreatingNew, selectedLotteryId]);

  const selectedLottery = useMemo(
    () => data.lotteries.find((item) => item.id === selectedLotteryId) ?? null,
    [data.lotteries, selectedLotteryId],
  );

  useEffect(() => {
    if (!selectedLottery || isCreatingNew) {
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
      prize_source: selectedLottery.prize_source,
      starts_at: selectedLottery.starts_at,
      entry_deadline_at: selectedLottery.entry_deadline_at,
      draw_at: selectedLottery.draw_at,
      prizes: selectedLottery.prizes.map((prize, index) => ({
        title: prize.title,
        winner_count: prize.winner_count,
        bonus_points: prize.bonus_points ?? 0,
        sort_order: prize.sort_order ?? index,
      })),
    });
  }, [isCreatingNew, selectedLottery]);

  const buildSubmitPayload = (): LotteryPayload => {
    const title = formState.title.trim();
    if (!title) {
      throw new Error("请先填写活动标题");
    }
    if (!formState.starts_at || !formState.entry_deadline_at) {
      throw new Error("请完整填写开始时间和报名截止时间");
    }
    const startsAt = new Date(formState.starts_at);
    const deadlineAt = new Date(formState.entry_deadline_at);
    const drawAt = new Date(formState.draw_at || formState.entry_deadline_at);
    if (Number.isNaN(startsAt.getTime()) || Number.isNaN(deadlineAt.getTime()) || Number.isNaN(drawAt.getTime())) {
      throw new Error("活动时间格式无效，请重新选择");
    }
    if (deadlineAt.getTime() < startsAt.getTime()) {
      throw new Error("报名截止时间不能早于开始时间");
    }
    if (drawAt.getTime() < deadlineAt.getTime()) {
      throw new Error("开奖时间不能早于报名截止时间");
    }
    const prizes = formState.prizes
      .map((prize, index) => ({
        title: prize.title.trim(),
        winner_count: Math.max(Number(prize.winner_count || 0), 0),
        bonus_points: Math.max(Number(prize.bonus_points || 0), 0),
        sort_order: index,
      }))
      .filter((prize) => prize.title);
    if (prizes.length === 0) {
      throw new Error("请至少配置一个奖项");
    }
    return {
      ...formState,
      title,
      description: formState.description.trim(),
      points_cost: Math.max(Number(formState.points_cost || 0), 0),
      points_threshold: Math.max(Number(formState.points_threshold || 0), 0),
      max_entries_per_user: Math.max(Number(formState.max_entries_per_user || 1), 1),
      starts_at: startsAt.toISOString(),
      entry_deadline_at: deadlineAt.toISOString(),
      draw_at: drawAt.toISOString(),
      prizes,
    };
  };

  const handleCreate = async () => {
    try {
      const payload = buildSubmitPayload();
      await onCreateLottery(payload);
      setIsCreatingNew(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "发布活动失败");
    }
  };

  const handleUpdate = async () => {
    if (!selectedLottery) return;
    try {
      const payload = buildSubmitPayload();
      await onUpdateLottery(selectedLottery.id, payload);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存活动失败");
    }
  };

  const handleCancel = async () => {
    if (!selectedLottery) return;
    try {
      await onCancelLottery(selectedLottery.id);
      setIsCreatingNew(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "取消活动失败");
    }
  };

  const handleDraw = async () => {
    if (!selectedLottery) return;
    try {
      await onDrawLottery(selectedLottery.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "开奖失败");
    }
  };

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
                setIsCreatingNew(true);
                setSelectedLotteryId(null);
                setFormState({
                  ...emptyPayload,
                  prizes: emptyPayload.prizes.map((item) => ({ ...item })),
                });
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
            <div className="space-y-2">
              <Label>奖池来源</Label>
              <Select value={formState.prize_source} onValueChange={(value: LotteryPayload["prize_source"]) => setFormState((prev) => ({ ...prev, prize_source: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="personal_points">普通奖励</SelectItem>
                  <SelectItem value="group_pool">群资金池</SelectItem>
                </SelectContent>
              </Select>
              {formState.prize_source === "group_pool" ? (
                <p className="text-xs text-muted-foreground">当前群资金池余额：{data.pointsPool?.balance ?? 0}</p>
              ) : null}
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <DateTimePicker label="开始时间" value={formState.starts_at} onChange={(next) => setFormState((prev) => ({ ...prev, starts_at: next }))} />
              <DateTimePicker label="报名截止" value={formState.entry_deadline_at} onChange={(next) => setFormState((prev) => ({ ...prev, entry_deadline_at: next }))} />
              <DateTimePicker label="开奖时间" value={formState.draw_at} onChange={(next) => setFormState((prev) => ({ ...prev, draw_at: next }))} />
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
                        { title: `奖项 ${prev.prizes.length + 1}`, winner_count: 1, bonus_points: 0, sort_order: prev.prizes.length },
                        ],
                    }))
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  新增奖项
                </Button>
              </div>
              {formState.prizes.map((prize, index) => (
                <div key={`prize-${index}`} className="grid gap-3 rounded-xl border bg-background/70 p-4 md:grid-cols-[1fr_120px_120px_80px]">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">奖项名称</Label>
                    <Input
                      value={prize.title}
                      onChange={(e) =>
                        setFormState((prev) => ({
                          ...prev,
                          prizes: prev.prizes.map((item, i) => (i === index ? { ...item, title: e.target.value } : item)),
                        }))
                      }
                      placeholder="例如：一等奖、幸运奖"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">中奖名额</Label>
                    <Input
                      type="number"
                      value={prize.winner_count}
                      onChange={(e) =>
                        setFormState((prev) => ({
                          ...prev,
                          prizes: prev.prizes.map((item, i) => (i === index ? { ...item, winner_count: Number(e.target.value) } : item)),
                        }))
                      }
                      placeholder="人数"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">奖励积分</Label>
                    <Input
                      type="number"
                      value={prize.bonus_points ?? 0}
                      onChange={(e) =>
                        setFormState((prev) => ({
                          ...prev,
                          prizes: prev.prizes.map((item, i) => (i === index ? { ...item, bonus_points: Number(e.target.value) } : item)),
                        }))
                      }
                      placeholder="发给每位中奖者的积分"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">操作</Label>
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
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void handleCreate()}>
                <Gift className="mr-2 h-4 w-4" />
                发布新活动
              </Button>
              {selectedLottery ? (
                <>
                  <Button variant="outline" onClick={() => void handleUpdate()}>
                    保存当前活动
                  </Button>
                  <Button variant="destructive" onClick={() => void handleCancel()}>
                    取消活动
                  </Button>
                  <Button variant="outline" onClick={() => void handleDraw()}>
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
                      setIsCreatingNew(false);
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
