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

### 2. Create the Cloudflare Token

Open the API Tokens page:

<https://dash.cloudflare.com/profile/api-tokens>

Create a custom token with these values:

```text
Token name: cf-ip-access-sync work
Permission: Account -> Account Firewall Access Rules -> Edit
Account Resources: Include -> <your Cloudflare account>
```

Copy the token secret once. Cloudflare only shows it at creation time.

You also need the Cloudflare Account ID for the same account. Use the Account ID, not a Zone ID. If you do not know where it is, see Cloudflare's account ID guide:

<https://developers.cloudflare.com/fundamentals/account/find-account-and-zone-ids/>

### 3. Run Setup

Run:

```bash
cf-ip-access-sync setup
```

Setup prompts for the Account ID and token, stores the token in macOS Keychain, saves local config, shows current status, runs a dry run, and then asks before installing automatic background sync.

Useful defaults:

```text
profile: work
ip family: IPv4
sync interval: 900 seconds
LaunchAgent: install after successful dry run
```

You can prefill common values:

```bash
cf-ip-access-sync setup --profile work --account-id '<cloudflare_account_id>'
```

Typical dry-run output:

```text
family=ipv4 current_ip=<your_public_ipv4> action=dry_run detail=would_create
```

When setup installs automatic sync, it writes:

```text
~/Library/LaunchAgents/com.cf-ip-access-sync.work.plist
```

Logs go to:

```text
~/Library/Logs/cf-ip-access-sync/work.out.log
~/Library/Logs/cf-ip-access-sync/work.err.log
```

The LaunchAgent uses `RunAtLoad = true`. With the setup default, `StartInterval = 900`, so it runs at login and then every fifteen minutes while your user session is active.

## Scripted Setup

For non-interactive setup, keep using `configure --token-stdin`. Do not paste the token directly into your shell history as a bare command argument.

```bash
printf '%s' '<cloudflare_api_token>' | cf-ip-access-sync configure \
  --profile work \
  --account-id '<cloudflare_account_id>' \
  --interval 900 \
  --token-stdin

cf-ip-access-sync sync --profile work --dry-run
cf-ip-access-sync install-agent --profile work --interval 900
```

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

Test the installed LaunchAgent command without changing Cloudflare:

```bash
cf-ip-access-sync test-agent --profile work
```

This reads the installed plist, runs its exact `ProgramArguments` with `--dry-run`, and uses a sparse launchd-like environment instead of your interactive shell environment. It is the best local check that automatic sync can find the executable, config, Keychain token, and network access.

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

### `firewallaccessrules.api.duplicate_of_existing`

Cloudflare already has an IP Access Rule for the same IP address. Check:

```bash
cf-ip-access-sync status --profile work
```

If the output shows `unmanaged_ipv4_allow_for_current_ip`, the current IP is already allowed by a rule that does not contain this tool's managed marker. You can leave it as-is, delete the manual rule and rerun sync, or edit the existing rule's note to this tool's marker if you want this tool to manage it.

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

Test the installed LaunchAgent command:

```bash
cf-ip-access-sync test-agent --profile work
```

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
cf-ip-access-sync install-agent --profile work --interval 900
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
