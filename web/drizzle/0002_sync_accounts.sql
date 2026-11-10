CREATE TABLE `sync_accounts` (
	`username` text PRIMARY KEY NOT NULL,
	`salt` text NOT NULL,
	`auth_hash` text NOT NULL,
	`wrapped_code` text NOT NULL,
	`nonce` text NOT NULL
);
