import { useState } from "react";
import { ArrowDownCircle, ArrowUpCircle, Coins } from "lucide-react";
import type { AdminDataBundle } from "@/components/admin/types";
import { formatTime } from "@/lib/helpers";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  onRefresh: () => Promise<void>;
  onAdjustPool: (payload: { amount: number; reason: string }) => Promise<void>;
};

export function PoolManagePanel({ data, onRefresh, onAdjustPool }: Props) {
  const [direction, setDirection] = useState<"add" | "sub">("add");
  const [amount, setAmount] = useState("100");
  const [reason, setReason] = useState("");

  const signedAmount = direction === "add" ? Number(amount) : -Number(amount);

  return (
    <div className="flex flex-col gap-6">
      <Card className="admin-surface-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>资金池总览</CardTitle>
          <Button variant="outline" onClick={() => void onRefresh()}>
            刷新
          </Button>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border bg-background/80 p-6">
            <div className="text-sm text-muted-foreground">当前余额</div>
            <div className="mt-2 flex items-center gap-3">
              <Coins className="h-6 w-6 text-amber-500" />
              <span className="text-3xl font-semibold">{data.pointsPool?.balance ?? 0}</span>
            </div>
            <div className="mt-2 text-xs text-muted-foreground">最近更新：{formatTime(data.pointsPool?.updated_at)}</div>
          </div>
          <div className="rounded-2xl border bg-background/80 p-6">
            <div className="text-sm text-muted-foreground">最近流水数量</div>
            <div className="mt-2 text-3xl font-semibold">{data.pointsPoolLedger.length}</div>
            <div className="mt-2 text-xs text-muted-foreground">用于查看红包过期入池、抽奖扣减和后台调账。</div>
          </div>
        </CardContent>
      </Card>

      <Card className="admin-surface-card">
        <CardHeader>
          <CardTitle>手动调账</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button type="button" variant={direction === "add" ? "default" : "outline"} onClick={() => setDirection("add")}>
              <ArrowUpCircle className="mr-2 h-4 w-4" />
              加积分
            </Button>
            <Button type="button" variant={direction === "sub" ? "destructive" : "outline"} onClick={() => setDirection("sub")}>
              <ArrowDownCircle className="mr-2 h-4 w-4" />
              扣积分
            </Button>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>调整数量</Label>
              <Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>调整原因</Label>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="例如：活动补贴、手动修正" />
            </div>
          </div>
          <Button onClick={() => void onAdjustPool({ amount: signedAmount, reason: reason.trim() })}>
            <Coins className="mr-2 h-4 w-4" />
            提交调账
          </Button>
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
                <TableHead>ID</TableHead>
                <TableHead>变动</TableHead>
                <TableHead>余额</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>原因</TableHead>
                <TableHead>时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.pointsPoolLedger.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">暂无资金池流水</TableCell>
                </TableRow>
              ) : (
                data.pointsPoolLedger.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.id}</TableCell>
                    <TableCell className={row.change_amount >= 0 ? "text-emerald-600" : "text-rose-600"}>{row.change_amount}</TableCell>
                    <TableCell>{row.balance_after}</TableCell>
                    <TableCell>{row.event_type}</TableCell>
                    <TableCell>{row.reason || "-"}</TableCell>
                    <TableCell>{formatTime(row.created_at)}</TableCell>
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
