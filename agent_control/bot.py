import asyncio
import logging
import time

HELP = '''Remote Agent Control
/agents — configured agents
/projects — configured projects
/new <agent> <project> <instruction> — start a conversation
/sessions — your latest conversations
/status <session> — state and recent output
/logs <session> — last 3000 characters
/history <session> — recent runs
/ask <session> <instruction> — resume after a run finishes
/stop <session> — stop the active run
/help — this message

Example: /new codex myapp explain this repository
Session IDs are shown when a run starts. Only private chats are accepted.'''


class Bot:
    def __init__(self, cfg, store, runner, telegram):
        self.cfg, self.store, self.runner, self.telegram = cfg, store, runner, telegram

    async def handle(self, update):
        # Ignore edits, channel posts, group messages, and non-allowlisted senders.
        msg = update.get('message') or {}
        chat, sender = msg.get('chat', {}), msg.get('from', {})
        if chat.get('type') != 'private' or sender.get('id') not in self.cfg.users or sender.get('is_bot'):
            return
        text = msg.get('text', '').strip()
        if not text:
            return
        owner, chat_id = sender['id'], chat['id']
        cmd, _, rest = text.partition(' ')
        cmd = cmd.split('@')[0].lower()
        try:
            if cmd in ('/start', '/help'):
                reply = HELP
            elif cmd == '/agents':
                reply = 'Agents: ' + ', '.join(self.cfg.agents)
            elif cmd == '/projects':
                reply = 'Projects: ' + ', '.join(self.cfg.projects)
            elif cmd == '/new':
                parts = rest.split(maxsplit=2)
                if len(parts) != 3:
                    raise ValueError('Usage: /new <agent> <project> <instruction>')
                agent, project, prompt = parts
                if agent not in self.cfg.agents or project not in self.cfg.projects:
                    raise ValueError('Unknown alias. Use /agents and /projects.')
                self.runner.check(project)
                session = self.store.create(owner, chat_id, agent, project)
                rid = self.runner.start(session, prompt)
                reply = f"Started {agent} on {project}.\nSession: {session['id']} • run {rid}\n/stop {session['id']}"
            elif cmd == '/sessions':
                rows = self.store.sessions(owner)
                reply = '\n'.join(f"{s['id']} · {s['agent']}/{s['project']} · {(self.store.latest(s['id']) or {}).get('status', 'new')}" for s in rows) or 'No sessions yet. Use /new.'
            elif cmd in ('/status', '/logs', '/history', '/stop', '/ask'):
                parts = rest.split(maxsplit=1)
                if not parts:
                    raise ValueError(f'Usage: {cmd} <session>' + (' <instruction>' if cmd == '/ask' else ''))
                session = self.store.session(parts[0], owner)
                sid = session['id']
                row = self.store.latest(sid)
                if cmd == '/ask':
                    if len(parts) != 2:
                        raise ValueError('Usage: /ask <session> <instruction>')
                    if not session['native_id']:
                        raise ValueError('No resumable conversation ID was captured. Start a new session with /new.')
                    rid = self.runner.start(session, parts[1])
                    reply = f'Resuming {sid} • run {rid}'
                elif cmd == '/stop':
                    await self.runner.stop(sid)
                    reply = f'Stop requested for {sid}.'
                elif cmd == '/history':
                    reply = '\n'.join(f"Run {r['id']}: {r['status']} (exit {r['exit_code']})" for r in self.store.history(sid)) or 'No runs.'
                elif cmd == '/logs':
                    reply = (row or {}).get('output', '')[-3000:] or 'No output yet.'
                else:
                    reply = f"{sid} · {session['agent']}/{session['project']}\nState: {(row or {}).get('status', 'new')}\n{(row or {}).get('output', '')[-2600:]}"
            else:
                reply = 'Use /help for commands. Send follow-ups with /ask <session> <instruction>.'
        except ValueError as exc:
            reply = str(exc)
        await self.telegram.send(chat_id, reply)

    async def poll(self, stop):
        offset = self.store.offset()
        while not stop.is_set():
            try:
                updates = await self.telegram.call('getUpdates', offset=offset, timeout=25, allowed_updates=['message'])
                for update in updates:
                    if stop.is_set():
                        break
                    if update['update_id'] < offset:
                        continue
                    offset = update['update_id'] + 1
                    # At-most-once launch: persist BEFORE running a command.
                    # A crash here can drop a command, but will not execute it twice.
                    self.store.advance(offset)
                    msg = update.get('message') or {}
                    if time.time() - msg.get('date', 0) > 300:
                        continue  # Never replay stale launch requests after downtime.
                    try:
                        await self.handle(update)
                    except Exception as exc:
                        logging.warning('Update handling failed (%s); use /sessions to check state.', type(exc).__name__)
            except Exception as exc:
                logging.warning('Telegram polling failed (%s); retrying.', type(exc).__name__)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=5)
                except TimeoutError:
                    pass
