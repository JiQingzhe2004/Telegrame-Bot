"use client";

import { useEffect, useMemo, useState } from "react";
import dayjs from "dayjs";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Props = {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  placeholder?: string;
};

function parseValue(value: string) {
  const parsed = value ? dayjs(value) : dayjs();
  return parsed.isValid() ? parsed : dayjs();
}

function pad(v: number) {
  return String(v).padStart(2, "0");
}

export function DateTimePicker({ value, onChange, label, placeholder = "选择日期时间" }: Props) {
  const current = useMemo(() => parseValue(value), [value]);
  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState(current.startOf("month"));
  const [hour, setHour] = useState(pad(current.hour()));
  const [minute, setMinute] = useState(pad(current.minute()));

  useEffect(() => {
    setViewMonth(current.startOf("month"));
    setHour(pad(current.hour()));
    setMinute(pad(current.minute()));
  }, [current]);

  const start = viewMonth.startOf("month").startOf("week");
  const days = Array.from({ length: 42 }, (_, index) => start.add(index, "day"));

  const commit = (date: dayjs.Dayjs, nextHour = hour, nextMinute = minute) => {
    const next = date.hour(Number(nextHour)).minute(Number(nextMinute)).second(0).millisecond(0);
    onChange(next.toISOString());
  };

  const hours = Array.from({ length: 24 }, (_, index) => pad(index));
  const minutes = Array.from({ length: 12 }, (_, index) => pad(index * 5));

  return (
    <div className="flex flex-col gap-2">
      {label ? <Label>{label}</Label> : null}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" className="justify-start text-left font-normal">
            <CalendarDays data-icon="inline-start" />
            {value ? dayjs(value).format("YYYY-MM-DD HH:mm") : placeholder}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[360px] p-4" align="start">
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <Button type="button" variant="ghost" size="icon" onClick={() => setViewMonth((prev) => prev.subtract(1, "month"))}>
                <ChevronLeft />
              </Button>
              <div className="text-sm font-medium">{viewMonth.format("YYYY 年 MM 月")}</div>
              <Button type="button" variant="ghost" size="icon" onClick={() => setViewMonth((prev) => prev.add(1, "month"))}>
                <ChevronRight />
              </Button>
            </div>

            <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted-foreground">
              {["日", "一", "二", "三", "四", "五", "六"].map((weekday) => (
                <div key={weekday} className="py-1">
                  {weekday}
                </div>
              ))}
            </div>

            <div className="grid grid-cols-7 gap-1">
              {days.map((day) => {
                const inMonth = day.month() === viewMonth.month();
                const selected = day.isSame(current, "day");
                return (
                  <Button
                    key={day.format("YYYY-MM-DD")}
                    type="button"
                    variant={selected ? "default" : "ghost"}
                    className={cn("h-9 px-0", !inMonth && "text-muted-foreground opacity-50")}
                    onClick={() => commit(day)}
                  >
                    {day.date()}
                  </Button>
                );
              })}
            </div>

            <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-3">
              <div className="flex flex-col gap-2">
                <Label>小时</Label>
                <Select
                  value={hour}
                  onValueChange={(nextHour) => {
                    setHour(nextHour);
                    commit(current, nextHour, minute);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {hours.map((item) => (
                      <SelectItem key={item} value={item}>
                        {item}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label>分钟</Label>
                <Select
                  value={minute}
                  onValueChange={(nextMinute) => {
                    setMinute(nextMinute);
                    commit(current, hour, nextMinute);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {minutes.map((item) => (
                      <SelectItem key={item} value={item}>
                        {item}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                完成
              </Button>
            </div>

            <div className="flex flex-col gap-2">
              <Label>精确时间</Label>
              <Input
                type="text"
                value={dayjs(value || current.toISOString()).format("YYYY-MM-DD HH:mm")}
                onChange={(event) => {
                  const raw = event.target.value.trim();
                  const parsed = dayjs(raw.replace(" ", "T"));
                  if (parsed.isValid()) {
                    setHour(pad(parsed.hour()));
                    setMinute(pad(parsed.minute()));
                    setViewMonth(parsed.startOf("month"));
                    onChange(parsed.toISOString());
                  }
                }}
                placeholder="YYYY-MM-DD HH:mm"
              />
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
