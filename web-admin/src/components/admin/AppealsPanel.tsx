import type { AdminDataBundle } from "@/components/admin/types";
import { formatTime } from "@/lib/helpers";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Props = {
  data: AdminDataBundle;
};

export function AppealsPanel({ data }: Props) {
  return (
    <Card className="admin-surface-card">
      <CardHeader>
        <CardTitle>申诉与回滚</CardTitle>
      </CardHeader>
      <CardContent>
        {data.appeals.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-muted/20 px-6 py-10 text-center text-sm text-muted-foreground">
            暂无申诉记录
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {data.appeals.map((item) => (
              <div key={item.id} className="rounded-xl border bg-background/90 p-4 shadow-sm">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant="outline">#{item.id}</Badge>
                  <span className="text-sm text-muted-foreground">user: {item.user_id}</span>
                </div>
                <p className="text-sm leading-6">{item.message}</p>
                <p className="mt-2 text-xs text-muted-foreground">{formatTime(item.created_at)}</p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
