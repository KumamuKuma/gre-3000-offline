export function isSyncUsername(value: string) {
  return /^[a-z0-9][a-z0-9_-]{2,31}$/.test(value);
}
