import asyncio
from dataclasses import dataclass
import os
import signal

from .adapters import command, event


@dataclass
class Active:
    session: dict
    run_id: int
    task: asyncio.Task | None = None
    process: asyncio.subprocess.Process | None = None
    stopped: bool = False


class Runner:
    def __init__(self, cfg, store, telegram):
        self.cfg, self.store, self.telegram = cfg, store, telegram
        self.active = {}

    def check(self, project):
        if project not in self.cfg.projects:
            raise ValueError('Project is no longer configured.')
        if len(self.active) >= self.cfg.max_parallel:
            raise ValueError('Server is busy. Try again after a run finishes.')
        if any(a.session['project'] == project for a in self.active.values()):
            raise ValueError('That project already has an active run.')
        path = self.cfg.projects[project]
        if not path.is_dir() or path.resolve() != path:
            raise ValueError('Project directory is missing or has changed.')
        # Prevent concurrent aliases for the same working directory.
        if any(self.cfg.projects[a.session['project']] == path for a in self.active.values()):
            raise ValueError('That directory already has an active run.')

    def start(self, session, prompt):
        if not prompt.strip() or len(prompt) > 12000:
            raise ValueError('Provide a prompt between 1 and 12000 characters.')
        if session['agent'] not in self.cfg.agents:
            raise ValueError('Agent is no longer configured.')
        if session['id'] in self.active:
            raise ValueError('Session is running. Stop it or wait before sending a follow-up.')
        self.check(session['project'])
        active = Active(session, self.store.start(session['id']))
        self.active[session['id']] = active
        active.task = asyncio.create_task(self._run(active, prompt))
        return active.run_id

    async def stop(self, sid):
        active = self.active.get(sid)
        if not active:
            raise ValueError('Session is not running.')
        active.stopped = True
        if active.process:
            await self._terminate(active.process)

    async def _terminate(self, process):
        # Kill the entire process group, including shell/tool subprocesses.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.3)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()

    async def close(self):
        for active in list(self.active.values()):
            active.stopped = True
            if active.process:
                await self._terminate(active.process)
        await asyncio.gather(*(a.task for a in list(self.active.values())), return_exceptions=True)

    async def _report(self, active):
        message = None
        previous = ''
        while True:
            row = self.store.latest(active.session['id'])
            text = f"Session {active.session['id']} • {row['status']}\n{row['output'][-2900:]}"
            if text != previous:
                try:
                    if message is None:
                        message = await self.telegram.send(active.session['chat'], text)
                    else:
                        await self.telegram.edit(active.session['chat'], message, text)
                    previous = text
                except Exception:
                    # Telegram outages must never interrupt or rerun the agent.
                    pass
            await asyncio.sleep(self.cfg.progress_interval)

    async def _run(self, active, prompt):
        s, rid = active.session, active.run_id
        report = asyncio.create_task(self._report(active))
        status, code = 'failed', None
        spec = self.cfg.agents[s['agent']]
        try:
            env = {k: v for k, v in os.environ.items() if not k.startswith('TELEGRAM_')}
            active.process = await asyncio.create_subprocess_exec(
                *command(spec, s['native_id']), cwd=self.cfg.projects[s['project']], env=env,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, start_new_session=True, limit=262144)
            if active.stopped:
                await self._terminate(active.process)
            async with asyncio.timeout(self.cfg.timeout):
                if not active.stopped:
                    active.process.stdin.write(prompt.encode() + b'\n')
                    await active.process.stdin.drain()
                    active.process.stdin.close()
                failed, total = False, 0
                while raw := await active.process.stdout.readline():
                    total += len(raw)
                    if total > self.cfg.max_output_bytes:
                        status = 'output_limit'
                        self.store.append(rid, 'Run stopped: output limit exceeded.')
                        break
                    native, text, error = event(spec['kind'], raw.decode(errors='replace').rstrip())
                    failed |= error
                    if native:
                        self.store.native(s['id'], native)
                    if text:
                        self.store.append(rid, text.replace(self.cfg.token, '[REDACTED]')[:24000])
                if status != 'output_limit':
                    code = await active.process.wait()
                    status = 'completed' if code == 0 and not failed else 'failed'
        except TimeoutError:
            status = 'timed_out'
            self.store.append(rid, 'Run exceeded its configured time limit.')
        except FileNotFoundError:
            self.store.append(rid, 'Agent executable or project directory not found. Check server configuration and PATH.')
        except Exception as exc:
            self.store.append(rid, f'Runner error: {type(exc).__name__}. Check CLI installation and authentication on the server.')
        finally:
            if active.process:
                await self._terminate(active.process)
            if active.stopped:
                status = 'stopped'
            self.store.finish(rid, status, code)
            report.cancel()
            await asyncio.gather(report, return_exceptions=True)
            self.active.pop(s['id'], None)
            row = self.store.latest(s['id'])
            try:
                await self.telegram.send(s['chat'], f"Session {s['id']} • {status}\n{row['output'][-2900:]}\n\n/ask {s['id']} your next instruction")
            except Exception:
                pass  # Results remain available through /status and /logs.
