import asyncio
import logging
import time

from .i18n import error_text, normalize_language, status_text, text as translate


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
        language = self.store.language(owner)
        if language is None:
            language = normalize_language(sender.get('language_code'))
            self.store.set_language(owner, language)
        cmd, _, rest = text.partition(' ')
        cmd = cmd.split('@')[0].lower()
        try:
            if cmd in ('/start', '/help'):
                reply = translate(language, 'help')
            elif cmd in ('/language', '/lang'):
                requested = rest.strip().lower()
                aliases = {'en': 'en', 'english': 'en', 'ar': 'ar', 'arabic': 'ar', 'العربية': 'ar', 'الإنجليزية': 'en'}
                if not requested:
                    name = 'العربية' if language == 'ar' else 'English'
                    reply = translate(language, 'language_help', language=name)
                elif requested not in aliases:
                    reply = translate(language, 'language_invalid')
                else:
                    language = aliases[requested]
                    self.store.set_language(owner, language)
                    reply = translate(language, 'language_changed')
            elif cmd == '/agents':
                reply = translate(language, 'agents', items=', '.join(self.cfg.agents))
            elif cmd == '/projects':
                reply = translate(language, 'projects', items=', '.join(self.cfg.projects))
            elif cmd == '/new':
                parts = rest.split(maxsplit=2)
                if len(parts) != 3:
                    reply = translate(language, 'error_usage_new')
                    await self.telegram.send(chat_id, reply)
                    return
                agent, project, prompt = parts
                if agent not in self.cfg.agents or project not in self.cfg.projects:
                    reply = translate(language, 'error_unknown_alias')
                    await self.telegram.send(chat_id, reply)
                    return
                self.runner.check(project)
                session = self.store.create(owner, chat_id, agent, project)
                rid = self.runner.start(session, prompt)
                reply = translate(language, 'started', agent=agent, project=project, session=session['id'], run=rid)
            elif cmd == '/sessions':
                rows = self.store.sessions(owner)
                reply = '\n'.join(translate(language, 'session_line', session=s['id'], agent=s['agent'], project=s['project'],
                                           status=status_text(language, (self.store.latest(s['id']) or {}).get('status', 'new')))
                                  for s in rows) or translate(language, 'no_sessions')
            elif cmd in ('/status', '/logs', '/history', '/stop', '/ask'):
                parts = rest.split(maxsplit=1)
                if not parts:
                    reply = translate(language, 'error_usage_session', command=cmd,
                                 suffix=' <instruction>' if cmd == '/ask' else '')
                    await self.telegram.send(chat_id, reply)
                    return
                session = self.store.session(parts[0], owner)
                sid = session['id']
                row = self.store.latest(sid)
                if cmd == '/ask':
                    if len(parts) != 2:
                        reply = translate(language, 'error_usage_ask')
                        await self.telegram.send(chat_id, reply)
                        return
                    if not session['native_id']:
                        reply = translate(language, 'error_no_native')
                        await self.telegram.send(chat_id, reply)
                        return
                    rid = self.runner.start(session, parts[1])
                    reply = translate(language, 'resuming', session=sid, run=rid)
                elif cmd == '/stop':
                    await self.runner.stop(sid)
                    reply = translate(language, 'stop_requested', session=sid)
                elif cmd == '/history':
                    reply = '\n'.join(translate(language, 'history_line', run=r['id'], status=status_text(language, r['status']),
                                               exit_code=r['exit_code']) for r in self.store.history(sid)) or translate(language, 'no_runs')
                elif cmd == '/logs':
                    reply = (row or {}).get('output', '')[-3000:] or translate(language, 'no_output')
                else:
                    reply = translate(language, 'status', session=sid, agent=session['agent'], project=session['project'],
                                 status=status_text(language, (row or {}).get('status', 'new')),
                                 output=(row or {}).get('output', '')[-2600:])
            else:
                reply = translate(language, 'unknown_command')
        except ValueError as exc:
            reply = error_text(language, str(exc))
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
