import { useMemo, useState } from "react";
import { AutoComplete } from "antd";
import type { ChatMemberBrief } from "@/lib/api";

type Props = {
  members: ChatMemberBrief[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxSeedOptions?: number;
  batchSize?: number;
};

export function UserLazySelect({
  members,
  value,
  onChange,
  placeholder = "支持搜索用户名/ID，也可手输",
  maxSeedOptions = 200,
  batchSize = 50,
}: Props) {
  const [open, setOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [visibleCount, setVisibleCount] = useState(batchSize);

  const allOptions = useMemo(
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

  const filteredOptions = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();
    if (!keyword) return allOptions;
    return allOptions.filter((item) => item.label.toLowerCase().includes(keyword));
  }, [allOptions, searchText]);

  const visibleOptions = useMemo(() => filteredOptions.slice(0, visibleCount), [filteredOptions, visibleCount]);

  const resetWindow = () => {
    setVisibleCount(batchSize);
  };

  const loadMore = () => {
    if (visibleCount >= filteredOptions.length) return;
    setVisibleCount((prev) => Math.min(prev + batchSize, filteredOptions.length));
  };

  return (
    <AutoComplete
      options={visibleOptions}
      value={value}
      style={{ width: "100%" }}
      placeholder={placeholder}
      open={open}
      filterOption={false}
      onChange={onChange}
      onFocus={() => {
        setOpen(true);
        resetWindow();
      }}
      onBlur={() => setOpen(false)}
      onSelect={() => setOpen(false)}
      onSearch={(next) => {
        setSearchText(next);
        setOpen(true);
        resetWindow();
      }}
      onPopupScroll={(e) => {
        const target = e.target as HTMLDivElement;
        const nearBottom = target.scrollTop + target.clientHeight >= target.scrollHeight - 24;
        if (nearBottom) loadMore();
      }}
      notFoundContent={searchText ? "未匹配到用户，可直接输入 ID" : "暂无可选用户"}
    />
  );
}
