import { index, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const progress = sqliteTable("progress", {
  ownerEmail: text("owner_email").primaryKey(),
  payload: text("payload").notNull(),
  updatedAt: text("updated_at").notNull(),
});

export const deviceTokens = sqliteTable(
  "device_tokens",
  {
    tokenHash: text("token_hash").primaryKey(),
    ownerEmail: text("owner_email").notNull(),
    label: text("label").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("device_tokens_owner_idx").on(table.ownerEmail)],
);
