CREATE TABLE `device_tokens` (
	`token_hash` text PRIMARY KEY NOT NULL,
	`owner_email` text NOT NULL,
	`label` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `device_tokens_owner_idx` ON `device_tokens` (`owner_email`);--> statement-breakpoint
CREATE TABLE `progress` (
	`owner_email` text PRIMARY KEY NOT NULL,
	`payload` text NOT NULL,
	`updated_at` text NOT NULL
);
