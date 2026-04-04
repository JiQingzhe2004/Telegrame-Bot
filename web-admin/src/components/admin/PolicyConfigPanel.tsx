import { useEffect, useState } from "react";
import { RefreshCw, Save } from "lucide-react";
import type { AdminActions, AdminDataBundle } from "@/components/admin/types";
import type { ChatSettings } from "@/lib/api";
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
import { Switch } from "@/components/ui/switch";

type Props = {
  data: AdminDataBundle;
  actions: AdminActions;
};

type PolicyFormState = Pick<
  ChatSettings,
  "mode" | "ai_enabled" | "ai_threshold" | "allow_admin_self_test" | "level3_mute_seconds"
>;

export function PolicyConfigPanel({ data, actions }: Props) {
  const settings = data.settings;
  const [formState, setFormState] = useState<PolicyFormState>({
    mode: "balanced",
    ai_enabled: true,
    ai_threshold: 0.5,
    allow_admin_self_test: false,
    level3_mute_seconds: 600,
  });

  useEffect(() => {
    if (!settings) return;
    setFormState({
      mode: settings.mode,
      ai_enabled: settings.ai_enabled,
      ai_threshold: settings.ai_threshold,
      allow_admin_self_test: settings.allow_admin_self_test,
      level3_mute_seconds: settings.level3_mute_seconds,
    });
  }, [settings]);

  return (
    <Card className="admin-surface-card">
      <CardHeader>
        <CardTitle>策略配置</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-2">
            <Label>模式</Label>
            <Select
              value={formState.mode}
              onValueChange={(value) => setFormState((prev) => ({ ...prev, mode: value as ChatSettings["mode"] }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="请选择模式" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="strict">strict</SelectItem>
                  <SelectItem value="balanced">balanced</SelectItem>
                  <SelectItem value="relaxed">relaxed</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>AI 阈值</Label>
            <Input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={formState.ai_threshold}
              onChange={(e) => setFormState((prev) => ({ ...prev, ai_threshold: Number(e.target.value) }))}
            />
          </div>

          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-1">
                <Label className="text-sm font-semibold">AI 开关</Label>
                <p className="text-xs text-muted-foreground">控制当前群是否启用 AI 审计。</p>
              </div>
              <Switch
                checked={formState.ai_enabled}
                onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, ai_enabled: checked }))}
              />
            </div>
          </div>

          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-1">
                <Label className="text-sm font-semibold">管理员自测模式</Label>
                <p className="text-xs text-muted-foreground">开启后，管理员消息也会进入 AI/审计链路，但不会执行真实处罚。</p>
              </div>
              <Switch
                checked={formState.allow_admin_self_test}
                onCheckedChange={(checked) => setFormState((prev) => ({ ...prev, allow_admin_self_test: checked }))}
              />
            </div>
          </div>

          <div className="space-y-2 md:col-span-2">
            <Label>L3 禁言秒数</Label>
            <Input
              type="number"
              min="1"
              value={formState.level3_mute_seconds}
              onChange={(e) => setFormState((prev) => ({ ...prev, level3_mute_seconds: Number(e.target.value) }))}
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button onClick={() => void actions.updateSettings(formState)}>
            <Save className="mr-2 h-4 w-4" />
            保存策略配置
          </Button>
          <Button variant="outline" onClick={() => void actions.refreshAll()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新配置
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
