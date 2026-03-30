import dayjs from "dayjs";
import type { ApiError } from "@/lib/api";

export function formatTime(value?: string | null): string {
  if (!value) return "-";
  return dayjs(value).format("YYYY-MM-DD HH:mm:ss");
}

export function getErrorMessage(error: unknown, fallback = "请求失败"): string {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (typeof error === "object" && error !== null) {
    const maybeApi = error as Partial<ApiError>;
    if (maybeApi.message) return maybeApi.message;
  }
  return fallback;
}

export function readStorage(key: string, fallback = ""): string {
  const value = localStorage.getItem(key);
  return value ?? fallback;
}

export function writeStorage(key: string, value: string): void {
  localStorage.setItem(key, value);
}
