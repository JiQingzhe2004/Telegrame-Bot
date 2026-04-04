export const queryKeys = {
  runtime: (baseUrl: string) => ["runtime", baseUrl] as const,
  adminSession: (baseUrl: string, adminToken: string) => ["adminSession", baseUrl, adminToken] as const,
  runtimeConfig: (baseUrl: string, adminToken: string) => ["runtimeConfig", baseUrl, adminToken] as const,
  status: (baseUrl: string, adminToken: string) => ["status", baseUrl, adminToken] as const,
  chats: (baseUrl: string, adminToken: string) => ["chats", baseUrl, adminToken] as const,
  settings: (baseUrl: string, chatId: string, adminToken: string) => ["settings", baseUrl, chatId, adminToken] as const,
  overview: (baseUrl: string, chatId: string, adminToken: string) => ["overview", baseUrl, chatId, adminToken] as const,
  members: (baseUrl: string, chatId: string, keyword: string, adminToken: string) =>
    ["members", baseUrl, chatId, keyword, adminToken] as const,
  verificationQuestions: (baseUrl: string, chatId: string, adminToken: string) =>
    ["verificationQuestions", baseUrl, chatId, adminToken] as const,
  whitelist: (baseUrl: string, chatId: string, adminToken: string) => ["whitelist", baseUrl, chatId, adminToken] as const,
  blacklist: (baseUrl: string, chatId: string, adminToken: string) => ["blacklist", baseUrl, chatId, adminToken] as const,
  pointsConfig: (baseUrl: string, chatId: string, adminToken: string) => ["pointsConfig", baseUrl, chatId, adminToken] as const,
  pointsBalance: (baseUrl: string, chatId: string, userId: string, adminToken: string) =>
    ["pointsBalance", baseUrl, chatId, userId, adminToken] as const,
  pointsCheckinState: (baseUrl: string, chatId: string, userId: string, adminToken: string) =>
    ["pointsCheckinState", baseUrl, chatId, userId, adminToken] as const,
  pointsTasks: (baseUrl: string, chatId: string, userId: string, adminToken: string) =>
    ["pointsTasks", baseUrl, chatId, userId, adminToken] as const,
  pointsTaskConfig: (baseUrl: string, chatId: string, adminToken: string) => ["pointsTaskConfig", baseUrl, chatId, adminToken] as const,
  pointsShop: (baseUrl: string, chatId: string, adminToken: string) => ["pointsShop", baseUrl, chatId, adminToken] as const,
  pointsRedemptions: (baseUrl: string, chatId: string, userId: string, adminToken: string) =>
    ["pointsRedemptions", baseUrl, chatId, userId, adminToken] as const,
  pointsLeaderboard: (baseUrl: string, chatId: string, adminToken: string) => ["pointsLeaderboard", baseUrl, chatId, adminToken] as const,
  pointsLedger: (baseUrl: string, chatId: string, userId: string, adminToken: string) =>
    ["pointsLedger", baseUrl, chatId, userId, adminToken] as const,
  audits: (baseUrl: string, chatId: string, adminToken: string) => ["audits", baseUrl, chatId, adminToken] as const,
  enforcements: (baseUrl: string, chatId: string, adminToken: string) => ["enforcements", baseUrl, chatId, adminToken] as const,
  appeals: (baseUrl: string, chatId: string, adminToken: string) => ["appeals", baseUrl, chatId, adminToken] as const,
};
