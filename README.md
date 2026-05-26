# cf-ip-access-sync

`cf-ip-access-sync` is a small macOS Python CLI that keeps your current public laptop IP synced to a Cloudflare account-level IP Access Rule with action `Allow` (`mode = "whitelist"` in the API).

It uses Cloudflare account-level IP Access Rules because this matches the broad account-scope allow behavior requested for this workflow. It does not manage Zero Trust Access policies, Cloudflare DNS records, or WAF IP Lists.

## Security Caveat

An account-level Allow IP Access Rule is broad. It can bypass many Cloudflare security checks for the allowed source IP across the account. Use a limited Cloudflare API token, keep the managed note marker intact, and remove the rule when you no longer need it.

The tool only modifies or deletes rules whose notes contain the exact managed marker for the selected profile and IP family, such as:

```text
cf-ip-access-sync profile=work managed=true family=ipv4
```

Cloudflare tokens are stored in macOS Keychain by default. The token is never written to the config file, LaunchAgent plist, or logs. `CLOUDFLARE_API_TOKEN` overrides Keychain for temporary manual runs.

## Cloudflare Token

Create a Cloudflare API token with:

```text
Account Firewall Access Rules Write
```

Use the Cloudflare account ID, not a zone ID.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Configure

```bash
printf '%s' '<cloudflare_api_token>' | cf-ip-access-sync configure \
  --profile work \
  --account-id '<cloudflare_account_id>' \
  --token-stdin
```

Non-secret config is stored at:

```text
~/Library/Application Support/cf-ip-access-sync/config.json
```

The Keychain service name is `cf-ip-access-sync:<profile>` and the Keychain account is the Cloudflare account ID.

## Manual Sync

Preview changes without touching Cloudflare:

```bash
cf-ip-access-sync sync --profile work --dry-run
```

Apply the sync:

```bash
cf-ip-access-sync sync --profile work
```

IPv4 is the default. To also sync IPv6 for a run:

```bash
cf-ip-access-sync sync --profile work --ipv6
```

If your sites are still challenged while IPv4 is allowlisted, your laptop or network may be reaching Cloudflare over IPv6. Enable IPv6 syncing if that is the intended behavior.

## Status

```bash
cf-ip-access-sync status --profile work
```

This prints the config path, masked account ID, token source, detected public IPs, and managed Cloudflare rules.

## LaunchAgent

Install a per-user LaunchAgent:

```bash
cf-ip-access-sync install-agent --profile work --interval 300
```

The plist is written to:

```text
~/Library/LaunchAgents/com.cf-ip-access-sync.work.plist
```

Logs are written to:

```text
~/Library/Logs/cf-ip-access-sync/work.out.log
~/Library/Logs/cf-ip-access-sync/work.err.log
```

Uninstall it:

```bash
cf-ip-access-sync uninstall-agent --profile work
```

This is a per-user LaunchAgent. It runs while you are logged in. If the laptop is off, asleep, or logged out, stale allowed IPs remain until the next successful sync.

## Remove Managed Rules

This deletes only rules with the exact managed marker for the selected profile:

```bash
cf-ip-access-sync remove-managed-rule --profile work --confirm
```

## Troubleshooting

`401` or `403` token errors: confirm the token has `Account Firewall Access Rules Write` for the target account and that the account ID is correct.

No public IP detected: the resolver endpoints may be blocked or offline. The tool aborts without changing Cloudflare if detection fails.

IPv6 still challenged: Cloudflare may see your IPv6 source address. Run with `--ipv6` or configure IPv6 support if you want both families managed.

LaunchAgent not running: check `launchctl print gui/$(id -u)/com.cf-ip-access-sync.<profile>` and the log files under `~/Library/Logs/cf-ip-access-sync/`.

Keychain prompt or missing token: run `configure --token-stdin` again, or set `CLOUDFLARE_API_TOKEN` for one manual command.
