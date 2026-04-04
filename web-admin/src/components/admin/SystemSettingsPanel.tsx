import { useEffect, useState } from "react";
import { RefreshCw, Save } from "lucide-react";
import type { KnownChat } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Props = {
  baseUrl: string;
  chatId: string;
  knownChats: KnownChat[];
  onReloadChats: () => Promise<void>;
  onSaveConnection: (values: { baseUrl: string; chatId: string }) => void;
  runtimeState: "setup" | "active";
  lastSyncText: string;
};

export function SystemSettingsPanel({
  baseUrl,
  chatId,
  knownChats,
  onReloadChats,
  onSaveConnection,
  runtimeState,
  lastSyncText,
}: Props) {
  const [draftBaseUrl, setDraftBaseUrl] = useState(baseUrl);
  const [draftChatId, setDraftChatId] = useState(chatId);

  useEffect(() => setDraftBaseUrl(baseUrl), [baseUrl]);
  useEffect(() => setDraftChatId(chatId), [chatId]);

  return (
    <Card className="admin-surface-card">
      <CardHeader>
        <CardTitle>系统设置</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <Label>API 地址</Label>
            <Input value={draftBaseUrl} onChange={(e) => setDraftBaseUrl(e.target.value)} />
            <p className="text-xs text-muted-foreground">
              管理令牌改为登录页输入，这里只保留服务地址和当前群设置。
            </p>
          </div>

          <div className="space-y-2">
            <Label>当前 Chat</Label>
            <Select value={draftChatId || undefined} onValueChange={setDraftChatId}>
              <SelectTrigger>
                <SelectValue placeholder="请选择群聊" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {knownChats.map((item) => (
                    <SelectItem key={item.chat_id} value={String(item.chat_id)}>
                      {item.title ?? "未命名群"} ({item.chat_id})
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              自动获取只会列出机器人已接收到事件的群。首次使用时，先把机器人拉进群；若还没出现，在群里发一条消息或命令后再刷新。
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" onClick={() => void onReloadChats()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            自动获取 Chat
          </Button>
          <Button onClick={() => onSaveConnection({ baseUrl: draftBaseUrl, chatId: draftChatId })}>
            <Save className="mr-2 h-4 w-4" />
            保存连接配置
          </Button>
          <Badge
            variant={runtimeState === "active" ? "outline" : "secondary"}
            className={runtimeState === "active" ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-200" : ""}
          >
            {runtimeState.toUpperCase()}
          </Badge>
          <span className="text-sm text-muted-foreground">最近同步: {lastSyncText}</span>
        </div>
      </CardContent>
    </Card>
  );
}
