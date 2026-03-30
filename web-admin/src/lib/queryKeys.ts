export const queryKeys = {
  runtime: ["runtime"] as const,
  status: (adminToken: string) => ["status", adminToken] as const,
  chats: (adminToken: string) => ["chats", adminToken] as const,
  settings: (chatId: string) => ["settings", chatId] as const,
  overview: (chatId: string) => ["overview", chatId] as const,
  members: (chatId: string, keyword: string) => ["members", chatId, keyword] as const,
  whitelist: (chatId: string) => ["whitelist", chatId] as const,
  blacklist: (chatId: string) => ["blacklist", chatId] as const,
  audits: (chatId: string) => ["audits", chatId] as const,
  enforcements: (chatId: string) => ["enforcements", chatId] as const,
  appeals: (chatId: string) => ["appeals", chatId] as const,
};
