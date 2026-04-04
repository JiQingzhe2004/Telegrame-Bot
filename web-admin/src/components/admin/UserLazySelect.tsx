import { useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import type { ChatMemberBrief } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type Props = {
  members: ChatMemberBrief[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxSeedOptions?: number;
};

export function UserLazySelect({
  members,
  value,
  onChange,
  placeholder = "支持搜索用户名/ID，也可手输",
  maxSeedOptions = 200,
}: Props) {
  const [open, setOpen] = useState(false);

  const options = useMemo(
    () =>
      members.slice(0, maxSeedOptions).map((m) => {
        const displayName = m.username || `${m.first_name ?? ""} ${m.last_name ?? ""}`.trim() || "未知用户";
        return {
          value: String(m.user_id),
          label: `${displayName} (${m.user_id})`,
        };
      }),
    [members, maxSeedOptions],
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal text-muted-foreground"
        >
          <span className="truncate">
            {value
              ? options.find((item) => item.value === value)?.label ?? value
              : placeholder}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[360px] p-0" align="start">
        <Command shouldFilter>
          <CommandInput
            placeholder={placeholder}
            value={value}
            onValueChange={onChange}
          />
          <CommandList>
            <CommandEmpty>没有匹配的成员，继续输入可手动指定用户 ID。</CommandEmpty>
            <CommandGroup heading="成员候选">
              {options.map((item) => (
                <CommandItem
                  key={item.label}
                  value={`${item.value} ${item.label}`}
                  onSelect={() => {
                    onChange(item.value);
                    setOpen(false);
                  }}
                >
                  <Check className={cn("mr-2 h-4 w-4", value === item.value ? "opacity-100" : "opacity-0")} />
                  <span className="truncate">{item.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
