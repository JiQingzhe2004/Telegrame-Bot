import type { AdminDataBundle } from "@/components/admin/types";
import { formatTime } from "@/lib/helpers";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
};

function renderAiStatus(status: "skipped" | "success" | "failed") {
  if (status === "success") {
    return <Badge className="bg-emerald-500 text-white">成功</Badge>;
  }
  if (status === "failed") {
    return <Badge variant="destructive">失败</Badge>;
  }
  return <Badge variant="secondary">跳过</Badge>;
}

function renderLevel(level: number) {
  if (level >= 3) return <Badge variant="destructive">L3</Badge>;
  if (level === 2) return <Badge className="bg-amber-500 text-white">L2</Badge>;
  if (level === 1) return <Badge variant="outline">L1</Badge>;
  return <Badge variant="secondary">L0</Badge>;
}

export function AuditCenterPanel({ data }: Props) {
  return (
    <Card className="admin-surface-card">
      <CardHeader>
        <CardTitle>审计中心</CardTitle>
      </CardHeader>
      <CardContent>
        {data.audits.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-muted/20 px-6 py-10 text-center text-sm text-muted-foreground">
            暂无审计记录
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[80px]">ID</TableHead>
                <TableHead className="w-[120px]">用户</TableHead>
                <TableHead className="w-[120px]">AI 状态</TableHead>
                <TableHead className="w-[110px]">等级</TableHead>
                <TableHead>规则/AI</TableHead>
                <TableHead>AI 错误</TableHead>
                <TableHead className="w-[100px]">置信度</TableHead>
                <TableHead className="w-[180px]">时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.audits.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>#{row.id}</TableCell>
                  <TableCell>{row.user_id}</TableCell>
                  <TableCell>{renderAiStatus(row.ai_status)}</TableCell>
                  <TableCell>{renderLevel(row.final_level)}</TableCell>
                  <TableCell className="max-w-[280px] truncate">{row.rule_hit}</TableCell>
                  <TableCell className="max-w-[240px] truncate">{row.ai_error || "-"}</TableCell>
                  <TableCell>{Number(row.confidence).toFixed(2)}</TableCell>
                  <TableCell>{formatTime(row.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
