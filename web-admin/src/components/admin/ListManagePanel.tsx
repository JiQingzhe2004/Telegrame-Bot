import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { UserLazySelect } from "@/components/admin/UserLazySelect";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Props = {
  data: AdminDataBundle;
  actions: AdminActions;
};

const PAGE_SIZE = 12;

type TagItem = {
  id: number;
  value: string;
};

function paginateItems(items: TagItem[], page: number) {
  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * PAGE_SIZE;
  return {
    totalPages,
    page: safePage,
    items: items.slice(start, start + PAGE_SIZE),
  };
}

function TagPager({
  title,
  emptyText,
  items,
  page,
  onPageChange,
  onRemove,
  tone,
}: {
  title: string;
  emptyText: string;
  items: TagItem[];
  page: number;
  onPageChange: (page: number) => void;
  onRemove: (value: string) => void;
  tone: "neutral" | "danger";
}) {
  const paged = paginateItems(items, page);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{title}</p>
        <span className="text-xs text-muted-foreground">
          第 {paged.page}/{paged.totalPages} 页，共 {items.length} 项
        </span>
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
          {emptyText}
        </div>
      ) : (
        <div className="flex flex-wrap gap-3">
          {paged.items.map((item) => (
            <div
              key={item.id}
              className={[
                "group relative inline-flex min-h-10 max-w-full items-center rounded-full border px-4 py-2 pr-10 text-sm transition-colors",
                tone === "danger"
                  ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-200"
                  : "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-400/20 dark:bg-slate-500/10 dark:text-slate-200",
              ].join(" ")}
            >
              <span className="truncate">{item.value}</span>
              <button
                type="button"
                className={[
                  "absolute right-2 top-1/2 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded-full opacity-0 transition-opacity group-hover:opacity-100",
                  tone === "danger"
                    ? "bg-rose-100 text-rose-700 hover:bg-rose-200 dark:bg-rose-500/20 dark:text-rose-100 dark:hover:bg-rose-500/30"
                    : "bg-slate-200 text-slate-700 hover:bg-slate-300 dark:bg-slate-500/20 dark:text-slate-100 dark:hover:bg-slate-500/30",
                ].join(" ")}
                aria-label={`删除 ${item.value}`}
                onClick={() => void onRemove(item.value)}
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={paged.page <= 1}
          onClick={() => onPageChange(paged.page - 1)}
        >
          上一页
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={paged.page >= paged.totalPages}
          onClick={() => onPageChange(paged.page + 1)}
        >
          下一页
        </Button>
      </div>
    </div>
  );
}

export function ListManagePanel({ data, actions }: Props) {
  const [white, setWhite] = useState("");
  const [black, setBlack] = useState("");
  const [whitePage, setWhitePage] = useState(1);
  const [blackPage, setBlackPage] = useState(1);

  return (
    <Card className="admin-surface-card">
      <CardHeader>
        <CardTitle>名单管理</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="whitelist" className="w-full">
          <TabsList className="mb-4 grid w-full grid-cols-2 md:w-[320px]">
            <TabsTrigger value="whitelist">白名单</TabsTrigger>
            <TabsTrigger value="blacklist">黑名单词</TabsTrigger>
          </TabsList>

          <TabsContent value="whitelist">
            <div className="flex flex-col gap-5">
              <div className="flex flex-col gap-3 sm:flex-row">
                <div className="flex-1">
                  <UserLazySelect
                    members={data.members}
                    value={white}
                    onChange={setWhite}
                    placeholder="@username 或 user_id（支持搜索）"
                  />
                </div>
                <Button onClick={() => void actions.addWhitelist(white)}>
                  <Plus className="mr-2 h-4 w-4" />
                  添加
                </Button>
              </div>

              <TagPager
                title="白名单标签"
                emptyText="暂无白名单"
                items={data.whitelist.map((item) => ({ id: item.id, value: item.value }))}
                page={whitePage}
                onPageChange={setWhitePage}
                onRemove={actions.removeWhitelist}
                tone="neutral"
              />
            </div>
          </TabsContent>

          <TabsContent value="blacklist">
            <div className="flex flex-col gap-5">
              <div className="flex flex-col gap-3 sm:flex-row">
                <div className="flex-1">
                  <Input
                    value={black}
                    onChange={(e) => setBlack(e.target.value)}
                    placeholder="违规词"
                  />
                </div>
                <Button variant="destructive" onClick={() => void actions.addBlacklist(black)}>
                  <Plus className="mr-2 h-4 w-4" />
                  添加
                </Button>
              </div>

              <TagPager
                title="黑名单标签"
                emptyText="暂无黑名单词"
                items={data.blacklist.map((item) => ({ id: item.id, value: item.value }))}
                page={blackPage}
                onPageChange={setBlackPage}
                onRemove={actions.removeBlacklist}
                tone="danger"
              />
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
