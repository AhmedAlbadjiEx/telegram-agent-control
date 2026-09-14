"""Headless CLI argument builders and event normalization."""
import json


def command(spec, native_id=None):
    args = list(spec['command'])
    kind = spec['kind']
    if kind == 'codex':
        # Global -c applies to both exec and exec resume.
        args += ['-c', 'approval_policy="never"', '-c', 'sandbox_mode="workspace-write"', 'exec']
        if native_id:
            args += ['resume', '--json', native_id, '-']
        else:
            args += ['--json', '-']
    elif kind == 'claude':
        args += ['-p', '--output-format', 'stream-json', '--verbose', '--permission-mode', 'acceptEdits']
        if native_id:
            args += ['--resume', native_id]
    elif native_id:
        raise ValueError('Generic adapters do not support native resume.')
    return args


def event(kind, line):
    """Return (session ID, display text, agent failure). Ignore reasoning content."""
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        return None, line, False
    if not isinstance(obj, dict):
        return None, line, False
    if kind == 'codex':
        typ = obj.get('type', '')
        if typ == 'thread.started':
            return obj.get('thread_id'), 'Conversation started', False
        if typ in ('error', 'turn.failed'):
            return None, 'Agent error: ' + str(obj.get('message') or obj.get('error')), True
        item = obj.get('item') or {}
        if typ.startswith('item.') and isinstance(item, dict):
            if item.get('type') == 'agent_message':
                return None, item.get('text', ''), False
            if item.get('type') == 'command_execution':
                return None, f"Command {item.get('status', '')}: {item.get('command', '')}", False
            if item.get('type') == 'file_change':
                return None, 'Files: ' + json.dumps(item.get('changes', [])), False
        return None, '', False
    if kind == 'claude':
        native = obj.get('session_id')
        if obj.get('type') == 'assistant':
            content = obj.get('message', {}).get('content', [])
            parts = [b.get('text', '') if b.get('type') == 'text' else 'Tool: ' + b.get('name', '')
                     for b in content if isinstance(b, dict) and b.get('type') in ('text', 'tool_use')]
            return native, '\n'.join(parts), False
        if obj.get('type') == 'result':
            denied = obj.get('permission_denials', [])
            text = obj.get('result') or '\n'.join(map(str, obj.get('errors', [])))
            if denied:
                text += '\nSome tools were denied by the configured CLI permissions.'
            return native, text, bool(obj.get('is_error'))
        return native, '', False
    return None, line, False
