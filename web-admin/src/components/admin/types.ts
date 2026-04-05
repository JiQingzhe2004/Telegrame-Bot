import type {
  AdminActionResult,
  AdminOverview,
  AppealRecord,
  AuditRecord,
  ChatMemberBrief,
  ChatPointsConfig,
  LotteryDetail,
  LotteryEntry,
  PointsCheckinState,
  ChatSettings,
  EnforcementRecord,
  ListItem,
  KnownChat,
  PointsBalance,
  PointsPacket,
  PointsPoolBalance,
  PointsPoolLedgerEntry,
  PointsLedgerEntry,
  PointsRedemption,
  PointsShopItem,
  PointsTaskDefinition,
} from "@/lib/api";

export type AdminDataBundle = {
  status?: Record<string, unknown>;
  knownChats: KnownChat[];
  settings?: ChatSettings;
  overview?: AdminOverview;
  members: ChatMemberBrief[];
  whitelist: ListItem[];
  blacklist: ListItem[];
  pointsConfig?: ChatPointsConfig;
  pointsCheckinState?: PointsCheckinState;
  pointsTasks: PointsTaskDefinition[];
  pointsTaskConfig: PointsTaskDefinition[];
  pointsShop: PointsShopItem[];
  pointsRedemptions: PointsRedemption[];
  pointsPackets: PointsPacket[];
  pointsPool?: PointsPoolBalance;
  pointsPoolLedger: PointsPoolLedgerEntry[];
  pointsLeaderboard: PointsBalance[];
  pointsLedger: PointsLedgerEntry[];
  lotteries: LotteryDetail[];
  lotteryEntries: LotteryEntry[];
  audits: AuditRecord[];
  enforcements: EnforcementRecord[];
  appeals: AppealRecord[];
  isLoading: boolean;
};

export type AdminActions = {
  refreshAll: () => Promise<void>;
  updateSettings: (payload: Partial<ChatSettings>) => Promise<void>;
  addWhitelist: (value: string) => Promise<void>;
  addBlacklist: (value: string) => Promise<void>;
  removeWhitelist: (value: string) => Promise<void>;
  removeBlacklist: (value: string) => Promise<void>;
  rollback: (enforcementId: number) => Promise<void>;
  runAction: (runner: () => Promise<AdminActionResult>, successText?: string) => Promise<void>;
};
