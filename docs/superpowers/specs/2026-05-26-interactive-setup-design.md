# Interactive Setup Design

## Goal

Make first-time setup easy and safe for a normal macOS user. The user should be able to create the Cloudflare token in the dashboard, run one command, paste the token securely, verify the intended Cloudflare change, and optionally install automatic background sync.

## Current Problems

- The README explains the underlying pieces but makes the user stitch together too many commands.
- Token creation guidance includes both direct dashboard links and extra documentation links, which makes the path feel less direct.
- The token name field in Cloudflare is not called out, so users have to invent a name.
- The only secure token setup path is a shell pipeline into `configure --token-stdin`, which is correct for scripting but awkward for first-time setup.
- Background sync is available, but it is not part of a guided first-run flow.

## Recommended Approach

Add `cf-ip-access-sync setup` as the primary first-run path. Keep existing commands (`configure`, `sync`, `status`, `install-agent`, `uninstall-agent`, and `remove-managed-rule`) for scripting, repair, and advanced use.

The setup command should be interactive and conservative:

1. Prompt for a profile name, defaulting to `work`.
2. Prompt for the Cloudflare Account ID.
3. Show the suggested Cloudflare token name: `cf-ip-access-sync <profile>`.
4. Show the direct Cloudflare token dashboard URL: `https://dash.cloudflare.com/profile/api-tokens`.
5. Show the required token permission: `Account -> Account Firewall Access Rules -> Edit`.
6. Prompt for the token with hidden input, then store it in macOS Keychain.
7. Ask whether to enable IPv6, defaulting to no.
8. Ask for the sync interval, defaulting to `900` seconds.
9. Save the profile config.
10. Run the equivalent of `status` so the user can see local config, token source, current IP detection, and any existing managed rule.
11. Run the equivalent of `sync --dry-run`.
12. Ask whether to install the LaunchAgent, defaulting to yes after a successful dry run.

## CLI Behavior

Add a new parser subcommand:

```text
cf-ip-access-sync setup
```

Options:

```text
--profile <name>       prefill the profile prompt
--account-id <id>      prefill the Account ID prompt
--interval <seconds>   prefill the interval prompt
--ipv6                 preselect IPv6
--no-agent             skip the LaunchAgent prompt and do not install it
```

If stdin is not a TTY, `setup` should fail with a clear error telling the user to use `configure --token-stdin` for non-interactive setup. Hidden token input should use `getpass.getpass()`.

Input validation should reuse existing profile and config validation where possible. Empty answers should accept defaults. Yes/no prompts should accept common short forms (`y`, `yes`, `n`, `no`) and repeat on invalid input.

## README Changes

Rewrite the Quick Start around the new happy path:

1. Install the CLI.
2. Create a Cloudflare token:
   - Open the direct token dashboard URL.
   - Use token name `cf-ip-access-sync work`.
   - Use permission `Account -> Account Firewall Access Rules -> Edit`.
   - Scope it to the intended account.
   - Copy the token once.
3. Run `cf-ip-access-sync setup`.
4. Confirm dry-run output.
5. Let setup install background sync.

Move the detailed Cloudflare documentation links to troubleshooting or reference instead of the main path. Keep the account ID guide only where it directly helps the user find the Account ID.

Keep the safety note, managed marker explanation, daily-use commands, IPv6 notes, files-created section, and troubleshooting, but reduce repetition where the setup command now handles the workflow.

## Error Handling

- If Keychain storage fails, show the Keychain error and do not continue to Cloudflare checks.
- If IP detection fails during status or dry run, keep the saved config and token but explain that no Cloudflare change was made.
- If Cloudflare returns `401` or `403`, tell the user to check the token permission, token account scope, Account ID, and token expiration.
- If the dry run fails, do not install the LaunchAgent.
- If LaunchAgent installation fails after successful config, report the error and leave the saved config and token intact.

## Testing

Add focused tests for the setup helpers rather than driving the whole CLI through real interactive stdin:

- Default prompt values, including `profile=work` and `interval=900`.
- Yes/no parsing.
- Non-TTY setup rejection.
- Setup config construction for IPv4-only and IPv4+IPv6 profiles.
- LaunchAgent installation skipped when dry run fails.

Existing tests should continue to cover payloads, rule selection safety, IP validation, and LaunchAgent plist generation.

## Out of Scope

- Automatically opening Cloudflare in a browser.
- Creating Cloudflare API tokens programmatically.
- Replacing existing script-friendly commands.
- Changing Cloudflare rule semantics or managed marker format.
