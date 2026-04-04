import { useMemo, useState } from "react";
import { Pencil, Plus, RotateCcw, Sparkles, Trash2 } from "lucide-react";
import type { VerificationQuestion } from "@/lib/api";
import { formatTime } from "@/lib/helpers";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type QuestionPayload = {
  scope: "chat" | "global";
  question: string;
  options: string[];
  answer_index: number;
};

type Props = {
  chatId?: string;
  loading: boolean;
  generating: boolean;
  questionType: "button" | "quiz";
  questions: VerificationQuestion[];
  onCreate: (payload: QuestionPayload) => Promise<void>;
  onUpdate: (questionId: number, payload: QuestionPayload) => Promise<void>;
  onDelete: (questionId: number) => Promise<void>;
  onGenerate: (payload: { scope: "chat" | "global"; count: number; topic_hint?: string }) => Promise<void>;
};

type FormValues = {
  scope: "chat" | "global";
  question: string;
  option_0: string;
  option_1: string;
  option_2: string;
  option_3: string;
  answer_original_index: string;
};

const OPTION_FIELDS = ["option_0", "option_1", "option_2", "option_3"] as const;

function toFormValues(item: VerificationQuestion): FormValues {
  return {
    scope: item.scope,
    question: item.question,
    option_0: item.options[0] ?? "",
    option_1: item.options[1] ?? "",
    option_2: item.options[2] ?? "",
    option_3: item.options[3] ?? "",
    answer_original_index: String(item.answer_index),
  };
}

export function VerificationQuestionPanel({
  chatId,
  loading,
  generating,
  questionType,
  questions,
  onCreate,
  onUpdate,
  onDelete,
  onGenerate,
}: Props) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [formState, setFormState] = useState<FormValues>({
    scope: "chat",
    question: "",
    option_0: "",
    option_1: "",
    option_2: "",
    option_3: "",
    answer_original_index: "",
  });
  const [generateState, setGenerateState] = useState({
    scope: "chat" as "chat" | "global",
    count: "3",
    topic_hint: "",
  });

  const filledOptions = useMemo(
    () =>
      OPTION_FIELDS.map((field, index) => ({
        originalIndex: index,
        text: String(formState[field] ?? "").trim(),
      })).filter((item) => item.text),
    [formState],
  );

  const answerChoices = filledOptions.map((item, index) => ({
    label: `${String.fromCharCode(65 + index)}. ${item.text}`,
    value: String(item.originalIndex),
  }));

  const resetForm = () => {
    setEditingId(null);
    setFormState({
      scope: "chat",
      question: "",
      option_0: "",
      option_1: "",
      option_2: "",
      option_3: "",
      answer_original_index: "",
    });
  };

  const buildPayload = (): QuestionPayload => {
    const optionPairs = OPTION_FIELDS.map((field, originalIndex) => ({
      originalIndex,
      text: String(formState[field] ?? "").trim(),
    })).filter((item) => item.text);

    if (!formState.question.trim()) {
      throw new Error("请填写题目");
    }
    if (optionPairs.length < 2 || optionPairs.length > 4) {
      throw new Error("请填写 2 到 4 个选项");
    }

    const answerOriginalIndex = Number(formState.answer_original_index);
    const answerIndex = optionPairs.findIndex((item) => item.originalIndex === answerOriginalIndex);
    if (answerIndex < 0) {
      throw new Error("请选择正确答案");
    }

    return {
      scope: formState.scope,
      question: formState.question.trim(),
      options: optionPairs.map((item) => item.text),
      answer_index: answerIndex,
    };
  };

  const handleSubmit = async () => {
    const payload = buildPayload();
    if (editingId === null) {
      await onCreate(payload);
    } else {
      await onUpdate(editingId, payload);
    }
    resetForm();
  };

  return (
    <>
      <Card className="admin-surface-card">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>入群验证题库</CardTitle>
            <p className="text-sm text-muted-foreground">当前题型模式为 {questionType === "quiz" ? "题库问答" : "按钮验证"}。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {chatId ? <Badge variant="outline">Chat {chatId}</Badge> : null}
            <Badge variant={questionType === "quiz" ? "outline" : "secondary"} className={questionType === "quiz" ? "border-sky-200 bg-sky-50 text-sky-700 dark:border-cyan-400/20 dark:bg-cyan-500/10 dark:text-cyan-200" : ""}>
              {questionType === "quiz" ? "当前使用题库模式" : "当前使用按钮模式"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <Alert>
            <AlertTitle>题库说明</AlertTitle>
            <AlertDescription>
              切到 quiz 后，会从当前群题库随机出题；当前群没有题时，会回退到全局题库；全都没有时再降级成按钮验证。
            </AlertDescription>
          </Alert>

          {questionType === "quiz" && questions.length === 0 ? (
            <Alert className="border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-100">
              <AlertTitle>题库为空</AlertTitle>
              <AlertDescription>quiz 模式下会自动降级成按钮验证。</AlertDescription>
            </Alert>
          ) : null}

          <Card className="border bg-background/60 shadow-none">
            <CardHeader>
              <CardTitle className="text-base">AI 生成题库</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>生成范围</Label>
                <Select
                  value={generateState.scope}
                  onValueChange={(value) => setGenerateState((prev) => ({ ...prev, scope: value as "chat" | "global" }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择范围" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="chat">当前群</SelectItem>
                      <SelectItem value="global">全局题库</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>生成数量</Label>
                <Input
                  type="number"
                  min="1"
                  max="5"
                  value={generateState.count}
                  onChange={(e) => setGenerateState((prev) => ({ ...prev, count: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>话题提示（可空）</Label>
                <Input
                  placeholder="例如：群规、技术交流、礼貌发言"
                  value={generateState.topic_hint}
                  onChange={(e) => setGenerateState((prev) => ({ ...prev, topic_hint: e.target.value }))}
                />
              </div>
              <div className="md:col-span-3">
                <Button
                  disabled={!chatId || generating || loading}
                  onClick={() =>
                    void onGenerate({
                      scope: generateState.scope,
                      count: Number(generateState.count),
                      topic_hint: generateState.topic_hint.trim() || undefined,
                    })
                  }
                >
                  <Sparkles className="mr-2 h-4 w-4" />
                  {generating ? "生成中..." : "使用当前 AI 配置生成题目"}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border bg-background/60 shadow-none">
            <CardHeader>
              <CardTitle className="text-base">{editingId === null ? "新增验证题" : `编辑验证题 #${editingId}`}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>范围</Label>
                  <Select
                    value={formState.scope}
                    onValueChange={(value) => setFormState((prev) => ({ ...prev, scope: value as "chat" | "global" }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="选择范围" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="chat">当前群</SelectItem>
                        <SelectItem value="global">全局题库</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>正确答案</Label>
                  <Select
                    value={formState.answer_original_index || undefined}
                    onValueChange={(value) => setFormState((prev) => ({ ...prev, answer_original_index: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="请选择正确答案" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {answerChoices.map((choice) => (
                          <SelectItem key={choice.value} value={choice.value}>
                            {choice.label}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>题目</Label>
                <Input
                  value={formState.question}
                  onChange={(e) => setFormState((prev) => ({ ...prev, question: e.target.value }))}
                  placeholder="请输入验证题目"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {OPTION_FIELDS.map((field, index) => (
                  <div key={field} className="space-y-2">
                    <Label>选项 {String.fromCharCode(65 + index)}</Label>
                    <Input
                      value={formState[field]}
                      onChange={(e) => setFormState((prev) => ({ ...prev, [field]: e.target.value }))}
                      placeholder={`请输入选项 ${String.fromCharCode(65 + index)}`}
                    />
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap gap-3">
                <Button disabled={loading} onClick={() => void handleSubmit()}>
                  {editingId === null ? <Plus className="mr-2 h-4 w-4" /> : <Pencil className="mr-2 h-4 w-4" />}
                  {editingId === null ? "新增验证题" : "保存修改"}
                </Button>
                <Button variant="outline" onClick={resetForm}>
                  <RotateCcw className="mr-2 h-4 w-4" />
                  重置表单
                </Button>
              </div>
            </CardContent>
          </Card>

          <div className="rounded-xl border bg-background/60">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[90px]">范围</TableHead>
                  <TableHead>题目</TableHead>
                  <TableHead>选项</TableHead>
                  <TableHead className="w-[220px]">正确答案</TableHead>
                  <TableHead className="w-[180px]">创建时间</TableHead>
                  <TableHead className="w-[150px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {questions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                      {loading ? "题库加载中..." : "暂无验证题"}
                    </TableCell>
                  </TableRow>
                ) : (
                  questions.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>
                        <Badge variant={row.scope === "global" ? "secondary" : "outline"}>
                          {row.scope === "global" ? "全局" : "当前群"}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[280px] truncate">{row.question}</TableCell>
                      <TableCell className="max-w-[260px] truncate">{row.options.join(" / ")}</TableCell>
                      <TableCell>{row.answer_text ?? "-"}</TableCell>
                      <TableCell>{formatTime(row.created_at)}</TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingId(row.id);
                              setFormState(toFormValues(row));
                            }}
                          >
                            <Pencil className="mr-2 h-4 w-4" />
                            编辑
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => setDeletingId(row.id)}>
                            <Trash2 className="mr-2 h-4 w-4" />
                            删除
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={deletingId !== null} onOpenChange={(open) => !open && setDeletingId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除验证题</DialogTitle>
            <DialogDescription>删除后不可恢复，确认继续吗？</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingId(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (deletingId === null) return;
                await onDelete(deletingId);
                setDeletingId(null);
              }}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
