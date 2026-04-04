import { Activity, ScanSearch, ShieldCheck, Users } from "lucide-react";
import type { AdminDataBundle } from "@/components/admin/types";
import { translatePermission } from "@/lib/helpers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  runtimeState: "setup" | "active";
  chatId: string;
  data: AdminDataBundle;
  onPermissionCheck: () => void;
  checking: boolean;
};

export function RunOverviewPanel({ runtimeState, chatId, data, onPermissionCheck, checking }: Props) {
  const metrics = [
    {
      title: "运行状态",
      value: runtimeState.toUpperCase(),
      icon: ShieldCheck,
    },
    {
      title: "当前 Chat",
      value: chatId || "-",
      icon: Activity,
    },
    {
      title: "成员池规模",
      value: String(data.members.length),
      icon: Users,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-3">
        {metrics.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.title} className="admin-metric-card border-none">
              <CardContent className="flex items-center justify-between p-6">
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground">{item.title}</p>
                  <p className="text-2xl font-semibold tracking-tight">{item.value}</p>
                </div>
                <div className="rounded-xl bg-primary/10 p-3 text-primary">
                  <Icon className="h-5 w-5" />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card className="admin-surface-card">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>群能力矩阵</CardTitle>
            <p className="text-sm text-muted-foreground">展示当前群的关键管理权限和机器人能力。</p>
          </div>
          <Button onClick={onPermissionCheck} disabled={checking}>
            <ScanSearch className="mr-2 h-4 w-4" />
            {checking ? "检查中..." : "权限一键自检"}
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[220px]">项目</TableHead>
                <TableHead>值</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="font-medium">群名</TableCell>
                <TableCell>{data.overview?.chat.title ?? "-"}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">成员数</TableCell>
                <TableCell>{data.overview?.member_count ?? "-"}</TableCell>
              </TableRow>
              {Object.entries(data.overview?.capabilities ?? {}).map(([name, ok]) => (
                <TableRow key={name}>
                  <TableCell className="font-medium">{translatePermission(name)}</TableCell>
                  <TableCell>
                    <Badge
                      variant={ok ? "outline" : "secondary"}
                      className={ok ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-200" : ""}
                    >
                      {ok ? "可用" : "不可用"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
