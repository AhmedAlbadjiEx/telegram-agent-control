import asyncio
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from agent_control.adapters import command, event
from agent_control.bot import Bot
from agent_control.config import Config
from agent_control.i18n import MESSAGES, normalize_language, status_text
from agent_control.runner import Runner
from agent_control.store import Store

class Telegram:
    def __init__(self): self.messages = []
    async def send(self, chat, text):
        self.messages.append((chat, text))
        return len(self.messages)
    async def edit(self, chat, message, text): self.messages.append((chat, text))

class Adapters(unittest.TestCase):
    def test_codex_resume(self):
        args = command({'kind':'codex','command':['codex']}, 'abc')
        self.assertEqual(args[-5:], ['exec','resume','--json','abc','-'])
        self.assertIn('sandbox_mode="workspace-write"', args)
    def test_claude_resume(self):
        args = command({'kind':'claude','command':['claude']}, 'abc')
        self.assertEqual(args[-2:], ['--resume','abc'])
        self.assertIn('acceptEdits', args)
    def test_protocol(self):
        self.assertEqual(event('codex','{"type":"thread.started","thread_id":"abc"}')[0], 'abc')
        self.assertTrue(event('codex','{"type":"turn.failed"}')[2])
        self.assertTrue(event('claude','{"type":"result","is_error":true}')[2])
        self.assertEqual(event('codex','bad')[1], 'bad')
        self.assertEqual(event('codex','[]')[1], '[]')
        self.assertEqual(event('codex','{"type":"item.completed","item":{"type":"reasoning","text":"hidden"}}')[1], '')

class Integration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cfg = Config('test-token', frozenset({1,2}), {'app':self.root}, {'fake':{'kind':'generic','command':[sys.executable,'-u','-c','import sys; print(sys.stdin.read())']}}, self.root)
        self.store = Store(self.root/'db')
        self.tg = Telegram()
        self.runner = Runner(self.cfg,self.store,self.tg)
        self.bot = Bot(self.cfg,self.store,self.runner,self.tg)
    async def asyncTearDown(self):
        await self.runner.close()
        self.store.db.close()
        self.tmp.cleanup()
    def update(self,text,owner=1,kind='private',language=None):
        sender = {'id':owner}
        if language:
            sender['language_code'] = language
        return {'message':{'from':sender,'chat':{'id':owner,'type':kind},'text':text,'date':time.time()}}
    async def complete(self):
        await asyncio.gather(*(a.task for a in list(self.runner.active.values())))
    def start(self,code=None):
        if code is not None: self.cfg.agents['fake']['command'] = [sys.executable,'-u','-c',code]
        s = self.store.create(1,1,'fake','app')
        self.runner.start(s,'hello')
        return s['id']
    async def test_allowlist(self):
        await self.bot.handle(self.update('/new fake app hello',owner=9))
        await self.bot.handle(self.update('/new fake app hello',kind='group'))
        self.assertFalse(self.store.sessions(1))
        self.assertFalse(self.store.sessions(9))
        self.assertFalse(self.tg.messages)
    async def test_prompt_not_shell(self):
        prompt = '$(touch HACKED); `touch HACKED`'
        await self.bot.handle(self.update('/new fake app '+prompt))
        await self.complete()
        row = self.store.latest(self.store.sessions(1)[0]['id'])
        self.assertEqual(row['status'],'completed')
        self.assertIn(prompt,row['output'])
        self.assertFalse((self.root/'HACKED').exists())
    async def test_owner_isolation(self):
        s = self.store.create(1,1,'fake','app')
        await self.bot.handle(self.update('/logs '+s['id'],owner=2))
        self.assertEqual(self.tg.messages[-1][1],'Session not found.')
    async def test_unknown_project(self):
        await self.bot.handle(self.update('/new fake ../../etc hello'))
        self.assertFalse(self.runner.active)
        self.assertIn('Unknown alias',self.tg.messages[-1][1])
    async def test_arabic_is_detected_and_persisted(self):
        await self.bot.handle(self.update('/help', language='ar-YE'))
        self.assertEqual(self.store.language(1), 'ar')
        self.assertIn('التحكم بالوكلاء', self.tg.messages[-1][1])
        await self.bot.handle(self.update('/new unknown app hello', language='en'))
        self.assertIn('اسم غير معروف', self.tg.messages[-1][1])
    async def test_language_command_changes_preference(self):
        await self.bot.handle(self.update('/language ar', language='en'))
        self.assertEqual(self.store.language(1), 'ar')
        self.assertIn('العربية', self.tg.messages[-1][1])
        await self.bot.handle(self.update('/language en', language='ar'))
        self.assertEqual(self.store.language(1), 'en')
        self.assertIn('English', self.tg.messages[-1][1])
    async def test_arabic_run_status_and_output(self):
        await self.bot.handle(self.update('/language ar'))
        await self.bot.handle(self.update('/new fake app مرحبا'))
        await self.complete()
        replies = '\n'.join(message for _, message in self.tg.messages)
        self.assertIn('بدأ تشغيل', replies)
        self.assertIn('مكتملة', replies)
        self.assertIn('مرحبا', replies)
    async def test_project_lock(self):
        self.start()
        with self.assertRaisesRegex(ValueError,'already has'): self.runner.check('app')
        await self.complete()
    async def test_stop_before_spawn(self):
        sid = self.start('import time; time.sleep(60)')
        await self.runner.stop(sid)
        await asyncio.wait_for(self.complete(),3)
        self.assertEqual(self.store.latest(sid)['status'],'stopped')
    async def test_timeout(self):
        self.cfg.timeout = 0.1
        sid = self.start('import time; time.sleep(60)')
        await self.complete()
        self.assertEqual(self.store.latest(sid)['status'],'timed_out')
    async def test_output_limit(self):
        self.cfg.max_output_bytes = 1024
        sid = self.start('print("x"*2000)')
        await self.complete()
        self.assertEqual(self.store.latest(sid)['status'],'output_limit')
    async def test_missing_executable(self):
        self.cfg.agents['fake']['command'] = ['/nonexistent/agent']
        sid = self.start()
        await self.complete()
        self.assertEqual(self.store.latest(sid)['status'],'failed')
    async def test_token_protection(self):
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test-token'
        try:
            sid = self.start('import os; print(os.getenv("TELEGRAM_BOT_TOKEN","absent")); print("test-token")')
            await self.complete()
            output = self.store.latest(sid)['output']
            self.assertIn('absent',output)
            self.assertNotIn('test-token',output)
        finally: del os.environ['TELEGRAM_BOT_TOKEN']
    async def test_capture_and_resume(self):
        script = self.root/'fake.py'
        script.write_text('import json,sys\nprint(json.dumps({"type":"thread.started","thread_id":"thread-123"}))\nprint(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":repr(sys.argv[1:])+sys.stdin.read()}}))\n')
        self.cfg.agents['fake'] = {'kind':'codex','command':[sys.executable,str(script)]}
        await self.bot.handle(self.update('/new fake app first'))
        await self.complete()
        s = self.store.sessions(1)[0]
        self.assertEqual(s['native_id'],'thread-123')
        await self.bot.handle(self.update('/ask '+s['id']+' follow up'))
        await self.complete()
        output = self.store.latest(s['id'])['output']
        self.assertIn("'resume'",output)
        self.assertIn('thread-123',output)
        self.assertIn('follow up',output)
    async def test_poll_deduplication_and_staleness(self):
        stop = asyncio.Event()
        fresh = dict(self.update('/new fake app hello'),update_id=10)
        old = dict(self.update('/new fake app stale'),update_id=11)
        old['message']['date'] -= 400
        calls = 0
        async def call(*args,**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1: return [fresh,fresh,old]
            stop.set()
            return []
        self.tg.call = call
        await self.bot.poll(stop)
        await self.complete()
        self.assertEqual(len(self.store.sessions(1)),1)
        self.assertEqual(self.store.offset(),12)
    async def test_notification_outage(self):
        async def fail(*args): raise RuntimeError('offline')
        self.tg.send = fail
        sid = self.start()
        await self.complete()
        self.assertEqual(self.store.latest(sid)['status'],'completed')
    async def test_restart_and_bounded_logs(self):
        sid = self.store.create(1,1,'fake','app')['id']
        rid = self.store.start(sid)
        self.store.append(rid,'x'*50000)
        self.store.advance(123)
        self.store.db.close()
        self.store = Store(self.root/'db')
        self.assertEqual(self.store.latest(sid)['status'],'interrupted')
        self.assertEqual(len(self.store.latest(sid)['output']),24000)
        self.assertEqual(self.store.offset(),123)

    async def test_stop_running_process_group(self):
        marker = self.root/'child.pid'
        code = 'import subprocess,time; p=subprocess.Popen(["'+sys.executable+'","-c","import time; time.sleep(60)"]); open("child.pid","w").write(str(p.pid)); time.sleep(60)'
        sid = self.start(code)
        for _ in range(100):
            if marker.exists(): break
            await asyncio.sleep(0.01)
        self.assertTrue(marker.exists())
        pid = int(marker.read_text())
        await self.runner.stop(sid)
        await asyncio.wait_for(self.complete(),3)
        self.assertEqual(self.store.latest(sid)['status'],'stopped')
        status = Path(f'/proc/{pid}/stat')
        if status.exists(): self.assertEqual(status.read_text().split()[2], 'Z')

class TelegramTextTests(unittest.TestCase):
    def test_emoji_limit(self):
        from agent_control.telegram import telegram_text
        output = telegram_text('😀'*4000)
        self.assertLessEqual(len(output.encode('utf-16-le')),7000)

class LocalizationTests(unittest.TestCase):
    def test_catalogs_have_the_same_messages(self):
        self.assertEqual(set(MESSAGES['en']), set(MESSAGES['ar']))

    def test_language_and_status_fallbacks(self):
        self.assertEqual(normalize_language('ar_YE'), 'ar')
        self.assertEqual(normalize_language('fr'), 'en')
        self.assertEqual(status_text('ar', 'running'), 'قيد التشغيل')
        self.assertEqual(status_text('ar', 'vendor_state'), 'vendor_state')
