import argparse
import asyncio
import fcntl
import logging
import os
import shutil
import signal

from .bot import Bot
from .config import Config
from .runner import Runner
from .store import Store
from .telegram import Telegram


async def serve(cfg):
    cfg.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(cfg.state_dir / 'bot.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another instance is using this state directory.')
        store = Store(cfg.state_dir / 'state.sqlite3')
        telegram = Telegram(cfg.token)
        runner = Runner(cfg, store, telegram)
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        logging.info('Bot started with %d projects and %d agents.', len(cfg.projects), len(cfg.agents))
        try:
            await Bot(cfg, store, runner, telegram).poll(stop)
        finally:
            await runner.close()
            store.db.close()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Control local coding agents through Telegram (Linux).')
    parser.add_argument('--config', default='config.toml')
    parser.add_argument('--check', action='store_true', help='Validate configuration and executable availability, without connecting')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        cfg = Config.load(args.config)
        if args.check:
            missing = [name for name, spec in cfg.agents.items() if not shutil.which(spec['command'][0])]
            if missing:
                raise ValueError('Executables not found for: ' + ', '.join(missing))
            print('Configuration and agent executables OK. Authentication is not checked.')
        else:
            asyncio.run(serve(cfg))
    except (ValueError, OSError) as exc:
        raise SystemExit(f'Configuration/startup error: {exc}') from None


if __name__ == '__main__':
    main()
