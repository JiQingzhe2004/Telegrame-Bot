import { useEffect, useState } from "react";
import { CheckCircle2, Coins, Gift, Minus, Plus, Search, ShoppingBag, Target } from "lucide-react";
import type {
  ChatPointsConfig,
  PointsBalance,
  PointsCheckinState,
  PointsLedgerEntry,
  PointsRedemption,
  PointsShopItem,
  PointsTaskDefinition,
} from "@/lib/api";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Props = {
  data: AdminDataBundle;
  balance?: PointsBalance;
  queriedUserId: string;
  setQueriedUserId: (value: string) => void;
  onRefresh: () => Promise<void>;
  onQueryBalance: () => Promise<void>;
  onSaveConfig: (payload: Partial<ChatPointsConfig>) => Promise<void>;
  onAdjustPoints: (payload: { user_id: string; amount: number; reason?: string }) => Promise<void>;
  onCheckin: (userId: string) => Promise<void>;
  onSaveTaskConfig: (items: PointsTaskDefinition[]) => Promise<void>;
  onSaveShop: (items: PointsShopItem[]) => Promise<void>;
  onRedeem: (userId: string, itemKey: string) => Promise<void>;
  onUpdateRedemptionStatus: (redemptionId: number, status: string) => Promise<void>;
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
  onCheckin,
  onSaveTaskConfig,
  onSaveShop,
  onRedeem,
  onUpdateRedemptionStatus,
}: Props) {
  const [configState, setConfigState] = useState<ChatPointsConfig>({
    points_enabled: true,
    points_message_reward: 1,
    points_message_cooldown_seconds: 60,
    points_daily_cap: 20,
    points_transfer_enabled: true,
    points_transfer_min_amount: 1,
    points_transfer_daily_limit: 10,
    points_checkin_base_reward: 3,
    points_checkin_streak_bonus: 1,
    points_checkin_streak_cap: 7,
  });
  const [adjustUserId, setAdjustUserId] = useState("");
  const [adjustAmount, setAdjustAmount] = useState("1");
  const [adjustReason, setAdjustReason] = useState("");
  const [taskConfig, setTaskConfig] = useState<PointsTaskDefinition[]>([]);
  const [shopItems, setShopItems] = useState<PointsShopItem[]>([]);

  useEffect(() => {
    if (data.pointsConfig) setConfigState(data.pointsConfig);
  }, [data.pointsConfig]);

  useEffect(() => {
    setTaskConfig(data.pointsTaskConfig);
  }, [data.pointsTaskConfig]);

  useEffect(() => {
    setShopItems(data.pointsShop);
  }, [data.pointsShop]);

  const adminOptions =
    data.overview?.administrators?.map((admin) => ({
      value: String(admin.user_id),
      label: `${admin.full_name} (${admin.user_id})`,
    })) ?? [];

  return (
    <div className="flex flex-col gap-6">
      <Tabs defaultValue="rules" className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-2 md:grid-cols-4">
          <TabsTrigger value="rules">规则配置</TabsTrigger>
          <TabsTrigger value="ledger">排行榜 / 流水</TabsTrigger>
          <TabsTrigger value="tasks">任务配置与统计</TabsTrigger>
          <TabsTrigger value="shop">商城商品与兑换记录</TabsTrigger>
        </TabsList>

        <TabsContent value="rules" className="space-y-6">
          <Card className="admin-surface-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>积分规则</CardTitle>
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
                  <Switch checked={configState.points_enabled} onCheckedChange={(checked) => setConfigState((prev) => ({ ...prev, points_enabled: checked }))} />
                </div>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <Label className="text-sm font-semibold">转账开关</Label>
                    <p className="text-xs text-muted-foreground">控制用户间是否允许转账。</p>
                  </div>
                  <Switch checked={configState.points_transfer_enabled} onCheckedChange={(checked) => setConfigState((prev) => ({ ...prev, points_transfer_enabled: checked }))} />
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
                <Label>每日发言上限</Label>
                <Input type="number" value={configState.points_daily_cap} onChange={(e) => setConfigState((prev) => ({ ...prev, points_daily_cap: Number(e.target.value) }))} />
              </div>
              <div className="space-y-2">
                <Label>最小转账额</Label>
                <Input type="number" value={configState.points_transfer_min_amount} onChange={(e) => setConfigState((prev) => ({ ...prev, points_transfer_min_amount: Number(e.target.value) }))} />
              </div>
              <div className="space-y-2">
                <Label>每日转账次数上限</Label>
                <Input type="number" value={configState.points_transfer_daily_limit} onChange={(e) => setConfigState((prev) => ({ ...prev, points_transfer_daily_limit: Number(e.target.value) }))} />
              </div>
              <div className="space-y-2">
                <Label>签到基础奖励</Label>
                <Input type="number" value={configState.points_checkin_base_reward} onChange={(e) => setConfigState((prev) => ({ ...prev, points_checkin_base_reward: Number(e.target.value) }))} />
              </div>
              <div className="space-y-2">
                <Label>连签额外奖励</Label>
                <Input type="number" value={configState.points_checkin_streak_bonus} onChange={(e) => setConfigState((prev) => ({ ...prev, points_checkin_streak_bonus: Number(e.target.value) }))} />
              </div>
              <div className="space-y-2">
                <Label>连签奖励上限天数</Label>
                <Input type="number" value={configState.points_checkin_streak_cap} onChange={(e) => setConfigState((prev) => ({ ...prev, points_checkin_streak_cap: Number(e.target.value) }))} />
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
              用户在群里执行 <code>/points</code>、<code>/checkin</code>、<code>/tasks</code>、<code>/shop</code> 时，详细信息都会优先私聊发送。用户如果还没和机器人建立私聊，需要先发送一次 <code>/start</code>。
            </CardContent>
          </Card>

          <Card className="admin-surface-card">
            <CardHeader>
              <CardTitle>余额查询与签到</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-3 sm:flex-row">
                <div className="flex-1">
                  <UserLazySelect members={data.members} extraOptions={adminOptions} value={queriedUserId} onChange={setQueriedUserId} placeholder="选择或输入用户 ID" />
                </div>
                <Button onClick={() => void onQueryBalance()}>
                  <Search className="mr-2 h-4 w-4" />
                  查询余额
                </Button>
                <Button variant="outline" disabled={!queriedUserId} onClick={() => void onCheckin(queriedUserId)}>
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  手动签到
                </Button>
              </div>
              {balance ? (
                <div className="grid gap-3 md:grid-cols-4">
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
                  <div className="rounded-xl border bg-background/70 p-4">
                    <div className="text-xs text-muted-foreground">连续签到</div>
                    <div className="mt-1 text-xl font-semibold">{data.pointsCheckinState?.streak_days ?? 0}</div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
                  选择成员后可查询余额与签到状态
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ledger" className="space-y-6">
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
        </TabsContent>

        <TabsContent value="tasks" className="space-y-6">
          <Card className="admin-surface-card">
            <CardHeader>
              <CardTitle>手动加减分</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <UserLazySelect members={data.members} extraOptions={adminOptions} value={adjustUserId} onChange={setAdjustUserId} placeholder="选择或输入用户 ID" />
              <Input type="number" value={adjustAmount} onChange={(e) => setAdjustAmount(e.target.value)} placeholder="正数加分，负数扣分" />
              <Input value={adjustReason} onChange={(e) => setAdjustReason(e.target.value)} placeholder="原因（可空）" />
              <Button onClick={() => void onAdjustPoints({ user_id: adjustUserId, amount: Number(adjustAmount), reason: adjustReason.trim() || undefined })}>
                <Plus className="mr-2 h-4 w-4" />
                执行调整
              </Button>
            </CardContent>
          </Card>

          <Card className="admin-surface-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>任务配置与统计</CardTitle>
              <Button variant="outline" onClick={() => void onSaveTaskConfig(taskConfig)}>
                <Target className="mr-2 h-4 w-4" />
                保存任务配置
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>任务</TableHead>
                    <TableHead>目标值</TableHead>
                    <TableHead>奖励</TableHead>
                    <TableHead>状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {taskConfig.map((task, index) => (
                    <TableRow key={task.task_key}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span>{task.title}</span>
                          <span className="text-xs text-muted-foreground">{task.description}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          value={task.target_value}
                          onChange={(e) =>
                            setTaskConfig((prev) =>
                              prev.map((item, i) => (i === index ? { ...item, target_value: Number(e.target.value) } : item)),
                            )
                          }
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          value={task.reward_points}
                          onChange={(e) =>
                            setTaskConfig((prev) =>
                              prev.map((item, i) => (i === index ? { ...item, reward_points: Number(e.target.value) } : item)),
                            )
                          }
                        />
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={task.enabled}
                          onCheckedChange={(checked) =>
                            setTaskConfig((prev) =>
                              prev.map((item, i) => (i === index ? { ...item, enabled: checked } : item)),
                            )
                          }
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="shop" className="space-y-6">
          <Card className="admin-surface-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>商城商品</CardTitle>
              <Button variant="outline" onClick={() => void onSaveShop(shopItems)}>
                <ShoppingBag className="mr-2 h-4 w-4" />
                保存商品配置
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>商品</TableHead>
                    <TableHead>价格</TableHead>
                    <TableHead>库存</TableHead>
                    <TableHead>启用</TableHead>
                    <TableHead>体验兑换</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {shopItems.map((item, index) => (
                    <TableRow key={item.item_key}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span>{item.title}</span>
                          <span className="text-xs text-muted-foreground">{item.description}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          value={item.price_points}
                          onChange={(e) =>
                            setShopItems((prev) =>
                              prev.map((entry, i) => (i === index ? { ...entry, price_points: Number(e.target.value) } : entry)),
                            )
                          }
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            disabled={item.stock === null}
                            onClick={() =>
                              setShopItems((prev) =>
                                prev.map((entry, i) =>
                                  i === index
                                    ? { ...entry, stock: Math.max((entry.stock ?? 0) - 1, 0) }
                                    : entry,
                                ),
                              )
                            }
                          >
                            <Minus className="h-4 w-4" />
                          </Button>
                          <Input
                            type="number"
                            value={item.stock ?? ""}
                            placeholder={item.stock === null ? "无限" : "库存"}
                            onChange={(e) =>
                              setShopItems((prev) =>
                                prev.map((entry, i) =>
                                  i === index
                                    ? { ...entry, stock: e.target.value === "" ? null : Math.max(Number(e.target.value), 0) }
                                    : entry,
                                ),
                              )
                            }
                            className="w-24 text-center"
                          />
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            disabled={item.stock === null}
                            onClick={() =>
                              setShopItems((prev) =>
                                prev.map((entry, i) =>
                                  i === index
                                    ? { ...entry, stock: (entry.stock ?? 0) + 1 }
                                    : entry,
                                ),
                              )
                            }
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          <Switch
                            checked={item.stock === null}
                            onCheckedChange={(checked) =>
                              setShopItems((prev) =>
                                prev.map((entry, i) =>
                                  i === index
                                    ? { ...entry, stock: checked ? null : 0 }
                                    : entry,
                                ),
                              )
                            }
                          />
                          <span className="text-xs text-muted-foreground">无限库存</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={item.enabled}
                          onCheckedChange={(checked) =>
                            setShopItems((prev) =>
                              prev.map((entry, i) => (i === index ? { ...entry, enabled: checked } : entry)),
                            )
                          }
                        />
                      </TableCell>
                      <TableCell>
                        <Button variant="outline" disabled={!queriedUserId} onClick={() => void onRedeem(queriedUserId, item.item_key)}>
                          <Gift className="mr-2 h-4 w-4" />
                          兑换
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card className="admin-surface-card">
            <CardHeader>
              <CardTitle>兑换记录</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>用户</TableHead>
                    <TableHead>商品ID</TableHead>
                    <TableHead>价格</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>过期时间</TableHead>
                    <TableHead>时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.pointsRedemptions.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground">暂无兑换记录</TableCell>
                    </TableRow>
                  ) : (
                    data.pointsRedemptions.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell>{row.user_id}</TableCell>
                        <TableCell>{row.item_id}</TableCell>
                        <TableCell>{row.price_points}</TableCell>
                        <TableCell>{row.status}</TableCell>
                        <TableCell>{row.expires_at || "-"}</TableCell>
                        <TableCell>{row.created_at}</TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            {row.status === "pending" ? (
                              <>
                                <Button size="sm" variant="outline" onClick={() => void onUpdateRedemptionStatus(row.id, "active")}>
                                  设为生效
                                </Button>
                                <Button size="sm" variant="destructive" onClick={() => void onUpdateRedemptionStatus(row.id, "rejected")}>
                                  拒绝
                                </Button>
                              </>
                            ) : row.status === "active" ? (
                              <Button size="sm" variant="outline" onClick={() => void onUpdateRedemptionStatus(row.id, "expired")}>
                                设为过期
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground">无可用操作</span>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
