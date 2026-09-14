"""Server-owned configuration: Telegram cannot supply executable paths or directories."""
import os
from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass
class Config:
    token: str
    users: frozenset[int]
    projects: dict[str, Path]
    agents: dict[str, dict]
    state_dir: Path
    max_parallel: int = 2
    timeout: int = 1800
    progress_interval: float = 5
    max_output_bytes: int = 2_000_000

    @classmethod
    def load(cls, path: str):
        with open(path, 'rb') as f:
            raw = tomllib.load(f)
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        users = frozenset(int(x) for x in os.environ.get('TELEGRAM_ALLOWED_USERS', '').split(',') if x.strip())
        if not token or not users or any(x <= 0 for x in users):
            raise ValueError('Set TELEGRAM_BOT_TOKEN and positive TELEGRAM_ALLOWED_USERS IDs.')
        projects = {k: Path(v).expanduser().resolve(strict=True) for k, v in raw.get('projects', {}).items()}
        if not projects or any(not p.is_dir() for p in projects.values()):
            raise ValueError('Configure at least one existing project directory.')
        agents = raw.get('agents', {})
        for name, spec in agents.items():
            if spec.get('kind') not in ('codex', 'claude', 'generic'):
                raise ValueError(f'Invalid agent kind: {name}')
            argv = spec.get('command')
            if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
                raise ValueError(f'Agent {name} needs a command array.')
        if not agents or any(not k.replace('-', '').replace('_', '').isalnum() for k in [*projects, *agents]):
            raise ValueError('Use simple alphanumeric aliases for agents and projects.')
        settings = raw.get('server', {})
        cfg = cls(token, users, projects, agents,
                  Path(settings.get('state_dir', '~/.local/state/telegram-agent-control')).expanduser().resolve(),
                  int(settings.get('max_parallel', 2)), int(settings.get('timeout_seconds', 1800)),
                  float(settings.get('progress_interval_seconds', 5)), int(settings.get('max_output_bytes', 2_000_000)))
        if cfg.max_parallel < 1 or cfg.timeout < 1 or cfg.progress_interval < 3 or cfg.max_output_bytes < 1024:
            raise ValueError('Invalid server limits.')
        return cfg
