CREATE TABLE `sync_spaces` (
	`space_id` text PRIMARY KEY NOT NULL,
	`auth_hash` text NOT NULL,
	`ciphertext` text NOT NULL,
	`nonce` text NOT NULL,
	`updated_at` text NOT NULL
);
