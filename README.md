# Telegram Remote Agent Control

[العربية](docs/README.ar.md)

Run Codex, Claude Code, and other headless agents on your Linux server from a private Telegram conversation. Start tasks, see progress, inspect recent output, stop work, and resume conversations.

**Status:** working initial implementation with automated process and protocol tests. Live Telegram and authenticated Codex/Claude operation must be verified on your server. This project manages conversations it starts; it does not attach to arbitrary existing terminals.

## Features

- Codex and Claude Code adapters with explicit conversation IDs for follow-ups.
- Generic stdin/stdout adapter for additional headless CLIs.
- Private-chat Telegram user allowlist and per-user session ownership.
- Named project directories configured on the server.
- Live progress messages and completion notifications, with `/logs` for recovery.
- SQLite session/run history, persisted polling offset, and restart interruption tracking.
- Global concurrency limit and one active run per project directory.
- Time/output limits and process-group termination.
- Outbound HTTPS long polling; no inbound port, public domain, or tunnel required.
- Python 3.11+ standard library only; no runtime pip dependencies.
- English and Arabic bot interfaces, with automatic Telegram-language detection and a saved per-user preference.

## Setup on Ubuntu/Linux

Use a dedicated non-root Linux account. Install Python 3.11+ and the coding-agent CLIs you want to use, then authenticate those CLIs as that same account. Verify `codex --version` and `claude --version`. Only configure installed agents; delete unused adapter sections.

Place this repository at `~/telegram-agent-control`. Clone your working repositories separately, for example into `~/projects/myapp`. Codex expects a Git working directory.

1. Open Telegram's verified **@BotFather**, use `/newbot`, and retain the bot token privately.
2. Obtain your numeric Telegram user ID (not your username). An ID helper such as @userinfobot can display it; never send that helper your bot token.
3. Configure the service:

```bash
cd ~/telegram-agent-control
cp .env.example .env
cp config.example.toml config.toml
chmod 600 .env config.toml
nano .env
nano config.toml
```

Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS` (comma-separated IDs), and an existing absolute directory for each project alias. Keep secrets out of Git. The program does not automatically parse `.env`; the shell or systemd supplies the environment.

4. Validate and run in your terminal:

```bash
set -a
. ./.env
set +a
python3 -m agent_control --check
python3 -m agent_control
```

5. Open your new bot in Telegram and send `/start`, then:

```text
/projects
/agents
/new codex myapp Explain this repository and suggest the first improvement
/sessions
/status SESSION_ID
/ask SESSION_ID Implement that improvement and run the tests
/stop SESSION_ID
/language ar
```

Replace `SESSION_ID` with the 12-character ID the bot returns. To use Claude:

```text
/new claude myapp Review the authentication code
```

To test setup before allowing edits, begin with an explanation or review request. `/new` and `/ask` can cause file modifications and tool execution under the CLI's configured permissions.

## Keep it running with systemd

Run these commands as the account that owns the agent CLI authentication:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/telegram-agent-control.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now telegram-agent-control
systemctl --user status telegram-agent-control
journalctl --user -u telegram-agent-control -f
```

To keep the user service running after logout, an administrator can enable lingering:

```bash
sudo loginctl enable-linger "$USER"
```

The supplied unit assumes `~/telegram-agent-control` and `/usr/bin/python3` >= 3.11. Adjust these if necessary. If a CLI was installed via nvm or a custom prefix, use its absolute executable path in `config.toml` and add any required Node runtime directory to the unit's `PATH`. Restart after configuration changes:

```bash
systemctl --user restart telegram-agent-control
```

The systemd unit kills remaining processes in its control group when stopped. Direct terminal runs also attempt process-group cleanup, but hard crashes outside systemd can leave processes; inspect the server before restarting a crashed foreground instance.

## Commands

| Command | Purpose |
| --- | --- |
| `/agents` | List configured agent aliases |
| `/projects` | List configured project aliases |
| `/new <agent> <project> <prompt>` | Start a new conversation |
| `/sessions` | Show your 20 newest sessions |
| `/ask <session> <prompt>` | Start the next turn in a completed/stopped conversation |
| `/status <session>` | Latest run status and output |
| `/logs <session>` | Most recent 3,000 characters |
| `/history <session>` | Most recent 10 run statuses |
| `/stop <session>` | Terminate the run and its process group |
| `/language <en\|ar>` | Save your preferred interface language |
| `/help` | Command reference |

The first private message uses the sender's Telegram language (`ar` selects Arabic; all other languages fall back to English). The choice is saved per allowlisted user. Use `/language ar` or `/language en` at any time to override it. Commands and configured aliases remain in ASCII so they work consistently in Telegram and server configuration; prompts and agent output fully support Arabic Unicode text.

Progress is edited about every five seconds when output changes. Agent tool events appear as the CLI emits them; this is not a token-by-token terminal mirror. Output is plain Telegram text. Recent output is capped at 24,000 characters per run; the total stream cap defaults to 2 MB and stops excessively verbose runs. Run metadata is retained indefinitely; back up and manage the SQLite database as needed.

## Agent permissions and extension

Codex runs with `approval_policy=never` and `sandbox_mode=workspace-write`. Here `never` means it cannot request interactive approval; it does **not** disable the sandbox. Claude uses `acceptEdits`: editing tools may run without a prompt, while other tools remain subject to its CLI permissions. Commands that require interactive approval can be denied. This initial version does not relay native approval dialogs to Telegram.

Review the local CLI configuration and trusted tools on the server. Do not add blanket permission-bypass flags merely to make a denied command work. Use appropriate isolation when processing untrusted repositories. A project alias controls the starting directory; it is not an OS security sandbox, especially for Claude or generic adapters.

Additional programs can use a generic adapter:

```toml
[agents.local]
kind = "generic"
command = ["/usr/local/bin/my-agent", "--headless"]
```

The command receives one prompt on standard input, followed by EOF, and must exit when finished. Arguments are passed directly without a shell. Generic adapters do not resume conversations. To integrate a new native session protocol, extend `agent_control/adapters.py` and add protocol tests.

## Reliability and security boundaries

- Accepts only allowlisted numeric users in private chats. Each user can inspect and control only sessions they own.
- Runs as the service's Linux user, with that user's agent credentials. Use a dedicated account with access only to intended projects.
- Telegram variables are removed from child-process environments and the bot token is redacted from stored output. This does not isolate files owned by the same OS user: agents may read `.env` if their permissions permit. Use a separate isolated execution boundary for hostile code.
- Bot conversations are not end-to-end encrypted. Agent responses and tool summaries go through Telegram. Avoid sending sensitive repositories or secrets through the bot.
- One bot process per token and state directory. A local file lock prevents concurrent instances using the same database; it cannot detect another server using the token.
- Polling offset is saved before dispatch to avoid duplicate agent launches. A crash between saving the offset and starting a run can drop that command; check `/sessions` before resubmitting. Requests older than five minutes are intentionally discarded.
- The bot does not retry agent jobs automatically. A Telegram notification failure does not change the run result; use `/sessions` and `/logs` after reconnecting.
- A restarted service marks unfinished runs `interrupted`. Resume requires the native conversation to have been saved by the CLI; if it was not saved, use `/new`.
- Stops attempt to terminate process groups. A tool deliberately detaching into another process group can escape this cleanup; the supplied systemd unit provides an additional control-group boundary on service shutdown.
- No arbitrary Telegram `/shell` endpoint, dynamic executable selection, or user-supplied working directory.

## Troubleshooting

**No response:** ensure `.env` contains your numeric ID, send messages privately, check the service log, and verify outbound access to `api.telegram.org`. Ensure this bot has no webhook configured and no other poller running; Telegram reports conflicts when polling cannot be used.

**CLI not found:** check executable paths and systemd's `PATH`. Run `--check` as the service user.

**Authentication or permission failure:** run the agent manually as the same user in the configured project and inspect its output. `/logs` displays captured diagnostics. Configure scoped CLI permissions if a necessary tool is denied.

**Follow-up rejected:** wait for the current run to finish. The initial run must have emitted a native conversation ID. Generic agents cannot use `/ask`.

**No live output:** some agents buffer text until a tool or response finishes. Use `/status`; a quiet process will eventually finish or hit its time limit.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m agent_control --help
```

Tests launch fake subprocesses and verify authorization, prompt handling, resume protocol, output bounds, timeout/stop behavior, polling deduplication, secret filtering, and notification failures. They require no Telegram token or paid agent calls. CI tests Python 3.11–3.13. Real vendor CLI compatibility and server-specific authentication still require a deployment smoke test.

Layout: `bot.py` handles commands; `runner.py` owns subprocesses; `adapters.py` translates CLI events; `store.py` persists history; `telegram.py` handles HTTPS; `config.py` validates local settings.

## Publish to GitHub

If this source was delivered as an archive, create a repository named `telegram-agent-control` on GitHub. A README-initialized repository can be populated through the GitHub connection in ChatGPT. Alternatively, with an authenticated GitHub CLI on your own computer, from this source directory:

```bash
git init -b main
git add .
git commit -m "Build Telegram remote agent control"
gh repo create telegram-agent-control --private --source=. --remote=origin --push
```

## Protocol references

- [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive)
- [Claude Code programmatic usage](https://code.claude.com/docs/en/headless)
- [Telegram Bot API](https://core.telegram.org/bots/api)

CLI interfaces can change; verify installed versions when upgrading.
