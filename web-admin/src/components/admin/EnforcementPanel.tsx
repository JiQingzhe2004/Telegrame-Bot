import { useState } from "react";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { formatTime } from "@/lib/helpers";
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
  actions: AdminActions;
};

export function EnforcementPanel({ data, actions }: Props) {
  const [pendingRollbackId, setPendingRollbackId] = useState<number | null>(null);

  return (
    <>
      <Card className="admin-surface-card">
        <CardHeader>
          <CardTitle>处置记录</CardTitle>
        </CardHeader>
        <CardContent>
          {data.enforcements.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-muted/20 px-6 py-10 text-center text-sm text-muted-foreground">
              暂无处置记录
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[80px]">ID</TableHead>
                  <TableHead className="w-[120px]">用户</TableHead>
                  <TableHead className="w-[120px]">动作</TableHead>
                  <TableHead>原因</TableHead>
                  <TableHead className="w-[180px]">时间</TableHead>
                  <TableHead className="w-[120px]">回滚</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.enforcements.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>#{row.id}</TableCell>
                    <TableCell>{row.user_id}</TableCell>
                    <TableCell>
                      <Badge variant={row.action === "ban" || row.action === "mute" ? "destructive" : "outline"}>
                        {row.action}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[320px] truncate">{row.reason}</TableCell>
                    <TableCell>{formatTime(row.created_at)}</TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!["mute", "restrict"].includes(row.action)}
                        onClick={() => setPendingRollbackId(row.id)}
                      >
                        回滚
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={pendingRollbackId !== null} onOpenChange={(open) => !open && setPendingRollbackId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认回滚</DialogTitle>
            <DialogDescription>
              {pendingRollbackId === null ? "" : `确认回滚处置 #${pendingRollbackId} 吗？`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingRollbackId(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (pendingRollbackId === null) return;
                await actions.rollback(pendingRollbackId);
                setPendingRollbackId(null);
              }}
            >
              确认回滚
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
