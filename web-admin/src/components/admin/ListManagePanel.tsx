import { useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import { UserLazySelect } from "@/components/admin/UserLazySelect";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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

export function ListManagePanel({ data, actions }: Props) {
  const [white, setWhite] = useState("");
  const [black, setBlack] = useState("");
  const blackOptions = useMemo(
    () => data.blacklist.map((item) => item.value),
    [data.blacklist],
  );

  const blackSuggestions = black
    ? blackOptions.filter((item) => item.toLowerCase().includes(black.toLowerCase())).slice(0, 8)
    : blackOptions.slice(0, 8);

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card className="admin-surface-card">
        <CardHeader>
          <CardTitle>白名单</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
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

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>值</TableHead>
                <TableHead className="w-[120px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.whitelist.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={2} className="text-center text-muted-foreground">
                    暂无白名单
                  </TableCell>
                </TableRow>
              ) : (
                data.whitelist.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.value}</TableCell>
                    <TableCell>
                      <Button variant="outline" size="sm" onClick={() => void actions.removeWhitelist(row.value)}>
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="admin-surface-card">
        <CardHeader>
          <CardTitle>黑名单词</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="flex-1 space-y-2">
              <Input
                value={black}
                onChange={(e) => setBlack(e.target.value)}
                placeholder="违规词（支持搜索）"
                list="blacklist-suggestions"
              />
              <datalist id="blacklist-suggestions">
                {blackSuggestions.map((item) => (
                  <option key={item} value={item} />
                ))}
              </datalist>
            </div>
            <Button variant="destructive" onClick={() => void actions.addBlacklist(black)}>
              <Plus className="mr-2 h-4 w-4" />
              添加
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>值</TableHead>
                <TableHead className="w-[120px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.blacklist.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={2} className="text-center text-muted-foreground">
                    暂无黑名单词
                  </TableCell>
                </TableRow>
              ) : (
                data.blacklist.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <Badge variant="destructive">{row.value}</Badge>
                    </TableCell>
                    <TableCell>
                      <Button variant="outline" size="sm" onClick={() => void actions.removeBlacklist(row.value)}>
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除
                      </Button>
                    </TableCell>
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
