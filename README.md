# cf-ip-access-sync

Keep your current Mac public IP allowed in Cloudflare with one account-level IP Access Rule.

`cf-ip-access-sync` is a small macOS CLI for laptops with changing public IPs. It detects your current public IP, stores your Cloudflare API token in macOS Keychain, and creates or updates a Cloudflare account-level IP Access Rule using:

```text
mode = whitelist
configuration.target = ip   # IPv4
configuration.target = ip6  # IPv6, optional
```

It intentionally does not use Zero Trust Access, DNS DDNS, or WAF IP Lists.

## What You Get

- Account-wide Cloudflare Allow rule for your current laptop IP.
- Safe updates with `PATCH` when your IP changes.
- Token storage in macOS Keychain, not in config files.
- A per-user LaunchAgent for automatic background sync while logged in.
- Dry-run and status commands before touching Cloudflare.
- Duplicate cleanup that only touches rules with this tool's exact managed marker.

## Important Safety Note

Cloudflare account-level Allow rules are broad. They can bypass many Cloudflare security checks for the allowed source IP across websites in the account. Use the smallest practical Cloudflare token scope, keep this tool's marker intact, and remove the managed rule when you no longer need it.

This tool will only modify or delete rules whose notes contain the exact managed marker for the selected profile and IP family:

```text
cf-ip-access-sync profile=work managed=true family=ipv4
```

It will not delete manually created rules or rules that merely contain `cf-ip-access-sync` without the exact marker.

## Cloudflare Links You Need

- Cloudflare dashboard: <https://dash.cloudflare.com>
- Create user API tokens: <https://dash.cloudflare.com/profile/api-tokens>
- Create account API tokens: <https://dash.cloudflare.com/?to=/:account/api-tokens>
- Cloudflare guide: create API tokens: <https://developers.cloudflare.com/fundamentals/api/get-started/create-token/>
- Cloudflare guide: account-owned tokens: <https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/>
- Cloudflare guide: find your Account ID: <https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/>
- Cloudflare API reference: IP Access Rules: <https://developers.cloudflare.com/api/resources/firewall/subresources/access_rules/>

Cloudflare's Access Rules API documents the `GET`, `POST`, `PATCH`, and `DELETE` endpoints for `/firewall/access_rules/rules`, plus `ip`, `ip6`, and `whitelist` rule fields.

## Quick Start

### 1. Install the CLI

From this checkout:

```bash
cd /Users/alejandro/Developer/GitHub/AlejandroAkbal/cf-ip-access-sync
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Or install the private GitHub repo with `pipx`:

```bash
brew install pipx
pipx ensurepath
pipx install "git+ssh://git@github.com/AlejandroAkbal/cf-ip-access-sync.git"
```

Check that the command is available:

```bash
cf-ip-access-sync --help
```

### 2. Get Your Cloudflare Account ID

Open Cloudflare's account ID guide:

<https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/>

Fast path in the dashboard:

1. Open <https://dash.cloudflare.com>.
2. Go to the account home page.
3. Copy the Account ID.

Use the Account ID, not a Zone ID.

### 3. Create the Cloudflare Token

Open the API Tokens page:

<https://dash.cloudflare.com/profile/api-tokens>

Create a custom token with this permission:

```text
Account -> Account Firewall Access Rules -> Edit
```

In Cloudflare API docs, this permission is named `Account Firewall Access Rules Write`.

Scope it to the Cloudflare account you copied above.

You can use a user API token or an account-owned token. Account-owned tokens are cleaner for durable automation, but Cloudflare requires account admin permissions to create them.

Copy the token secret once. Cloudflare only shows it at creation time.

### 4. Configure This Tool

This stores non-secret config in:

```text
~/Library/Application Support/cf-ip-access-sync/config.json
```

The token is stored in macOS Keychain under service `cf-ip-access-sync:work`.

```bash
printf '%s' '<cloudflare_api_token>' | cf-ip-access-sync configure \
  --profile work \
  --account-id '<cloudflare_account_id>' \
  --token-stdin
```

Do not paste the token directly into your shell history as a bare command argument. Pipe it through stdin as shown above.

### 5. Inspect Without Changing Cloudflare

```bash
cf-ip-access-sync status --profile work
cf-ip-access-sync sync --profile work --dry-run
```

Confirm the dry run shows the action you expect.

### 6. Sync Once

```bash
cf-ip-access-sync sync --profile work
```

Typical output:

```text
family=ipv4 current_ip=<your_public_ipv4> action=created rule_id=<cloudflare_rule_id>
```

Later, when your IP changes, the same managed rule is updated with `PATCH` instead of creating a new primary rule.

### 7. Install Automatic Sync

```bash
cf-ip-access-sync install-agent --profile work --interval 300
```

This writes:

```text
~/Library/LaunchAgents/com.cf-ip-access-sync.work.plist
```

Logs go to:

```text
~/Library/Logs/cf-ip-access-sync/work.out.log
~/Library/Logs/cf-ip-access-sync/work.err.log
```

The LaunchAgent uses `RunAtLoad = true` and `StartInterval = 300`, so it runs at login and then every five minutes while your user session is active.

## Daily Use

Check current state:

```bash
cf-ip-access-sync status --profile work
```

Run a manual sync:

```bash
cf-ip-access-sync sync --profile work
```

Preview a manual sync:

```bash
cf-ip-access-sync sync --profile work --dry-run
```

Enable IPv6 for one run:

```bash
cf-ip-access-sync sync --profile work --ipv6
```

Uninstall the LaunchAgent:

```bash
cf-ip-access-sync uninstall-agent --profile work
```

Remove only this profile's managed Cloudflare rules:

```bash
cf-ip-access-sync remove-managed-rule --profile work --confirm
```

## IPv4 and IPv6

IPv4 is the default because it matches the usual manual workflow: allowlist the public IPv4 address of the laptop's current network.

If Cloudflare still challenges you after IPv4 is allowlisted, your browser may be reaching Cloudflare over IPv6. Run:

```bash
cf-ip-access-sync sync --profile work --ipv6
```

IPv6 rules use the same profile safety model, but with this marker:

```text
cf-ip-access-sync profile=work managed=true family=ipv6
```

## How It Works

1. Acquires a per-profile lock file so two syncs do not race.
2. Reads non-secret config from Application Support.
3. Reads the token from `CLOUDFLARE_API_TOKEN` or macOS Keychain.
4. Detects the current public IP with multiple public IP resolvers.
5. Lists account-level Cloudflare IP Access Rules.
6. Filters locally by the exact managed note marker.
7. Creates, updates, leaves unchanged, or safely cleans up duplicate managed rules.

The Cloudflare API base URL is:

```text
https://api.cloudflare.com/client/v4
```

The account-level endpoint is:

```text
/accounts/{account_id}/firewall/access_rules/rules
```

## Files Created on Your Mac

Config:

```text
~/Library/Application Support/cf-ip-access-sync/config.json
```

Lock file:

```text
~/Library/Application Support/cf-ip-access-sync/<profile>.lock
```

LaunchAgent:

```text
~/Library/LaunchAgents/com.cf-ip-access-sync.<profile>.plist
```

Logs:

```text
~/Library/Logs/cf-ip-access-sync/<profile>.out.log
~/Library/Logs/cf-ip-access-sync/<profile>.err.log
```

Keychain:

```text
service: cf-ip-access-sync:<profile>
account: <cloudflare_account_id>
```

## Troubleshooting

### `401` or `403` from Cloudflare

Check:

- The token has `Account -> Account Firewall Access Rules -> Edit`.
- The token is scoped to the right Cloudflare account.
- You configured the Account ID, not a Zone ID.
- The token has not expired or been rolled.

Token docs: <https://developers.cloudflare.com/fundamentals/api/get-started/create-token/>

### No Public IP Detected

The tool aborts without changing Cloudflare if IP detection fails.

Try:

```bash
curl https://api.ipify.org
curl https://ipv4.icanhazip.com
curl https://checkip.amazonaws.com
```

If all fail, your network may be blocking these resolvers.

### IPv6 Still Gets Challenged

Check whether your network has IPv6:

```bash
curl https://api6.ipify.org
```

If it returns an IPv6 address, run:

```bash
cf-ip-access-sync sync --profile work --ipv6
```

### LaunchAgent Is Not Running

Inspect launchd:

```bash
launchctl print gui/$(id -u)/com.cf-ip-access-sync.work
```

Check logs:

```bash
tail -n 100 ~/Library/Logs/cf-ip-access-sync/work.err.log
tail -n 100 ~/Library/Logs/cf-ip-access-sync/work.out.log
```

Reload:

```bash
cf-ip-access-sync uninstall-agent --profile work
cf-ip-access-sync install-agent --profile work --interval 300
```

### Keychain Token Missing

Store it again:

```bash
printf '%s' '<cloudflare_api_token>' | cf-ip-access-sync configure \
  --profile work \
  --account-id '<cloudflare_account_id>' \
  --token-stdin
```

For a one-off command, override Keychain with an environment variable:

```bash
CLOUDFLARE_API_TOKEN='<cloudflare_api_token>' cf-ip-access-sync status --profile work
```

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

The test suite covers IP validation, rule selection safety, Cloudflare payloads, duplicate cleanup, dry-run behavior, and LaunchAgent plist generation.
