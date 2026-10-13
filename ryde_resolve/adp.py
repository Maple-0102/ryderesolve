"""Tencent ADP HTTP SSE adapter, based on the organizer's v02 integration guide.

One fresh conversation per case/run. Credentials never enter returned outputs/logs.
The published ADP application's system prompt must be configured separately.
"""
import json
import math
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from ryderesolve_evidence.core import parse_json
from .agents import AgentError, NoRedirect, ROOT, build_judge_messages

ENDPOINT = 'https://wss.lke.tencentcloud.com/adp/v2/chat'
KEY_FILE = ROOT / '.local' / 'adp-app-key'
MAX_RESPONSE = 2_000_000
MAX_LINE = 1_000_000


@dataclass(frozen=True)
class ADPConfig:
    app_key: str = field(repr=False)
    endpoint: str = ENDPOINT
    timeout: float = 120.0

    def __post_init__(self):
        u = urlsplit(self.endpoint)
        loopback = u.scheme == 'http' and u.hostname in {'127.0.0.1', 'localhost', '::1'}
        if self.endpoint != ENDPOINT and not (loopback and not u.username and not u.password and not u.query and not u.fragment):
            raise AgentError('ADP_ENDPOINT_NOT_ALLOWED')
        if not isinstance(self.app_key, str) or not self.app_key.strip() or any(c.isspace() for c in self.app_key):
            raise AgentError('ADP_APP_KEY_MISSING_OR_INVALID')
        if not math.isfinite(self.timeout) or not 0 < self.timeout <= 300:
            raise AgentError('ADP_INVALID_TIMEOUT')

    @classmethod
    def from_env(cls):
        key = os.environ.get('ADP_APP_KEY', '').strip()
        if not key:
            try:
                if KEY_FILE.is_symlink(): raise AgentError('ADP_KEY_FILE_UNSAFE')
                mode = KEY_FILE.stat().st_mode
                if os.name == 'posix' and stat.S_IMODE(mode) & 0o077:
                    raise AgentError('ADP_KEY_FILE_PERMISSIONS')
                if not stat.S_ISREG(mode) or KEY_FILE.stat().st_size > 8192:
                    raise AgentError('ADP_KEY_FILE_UNSAFE')
                key = KEY_FILE.read_text(encoding='utf-8').strip()
            except FileNotFoundError:
                raise AgentError('ADP_CONFIG_MISSING: run python -m ryde_resolve.adp_setup after publishing the ADP app') from None
            except (OSError, UnicodeError):
                raise AgentError('ADP_KEY_FILE_UNREADABLE') from None
        try:
            timeout = float(os.environ.get('ADP_TIMEOUT', '120'))
        except ValueError:
            raise AgentError('ADP_INVALID_TIMEOUT') from None
        return cls(key, os.environ.get('ADP_CHAT_URL', ENDPOINT), timeout)


def case_question(snapshot, arguments, calculations):
    # System instructions live in ADP configuration; case contents remain untrusted.
    return ('Process the following UNTRUSTED CASE DATA under your configured RydeResolve Judge '
            'instructions. Return exactly one Judge JSON object.\n' +
            build_judge_messages(snapshot, arguments, calculations)[1]['content'])


def _text(value):
    if isinstance(value, str): return value
    if not isinstance(value, dict): return ''
    for key in ('Text', 'Content', 'Delta', 'Reply', 'Answer', 'text', 'content', 'delta'):
        if key in value:
            v = value[key]
            if isinstance(v, list): return ''.join(_text(x) for x in v)
            if isinstance(v, (str, dict)): return _text(v)
    return ''


def _usage(response):
    raw = response.get('StatInfo', response.get('Usage', {}))
    if not isinstance(raw, dict): return {}
    result = {}
    for out, names in {'input_tokens': ('InputTokens', 'PromptTokens'),
                       'output_tokens': ('OutputTokens', 'CompletionTokens'),
                       'total_tokens': ('TotalTokens',), 'reported_total_cost': ('TotalCost',)}.items():
        for key in names:
            val = raw.get(key)
            if type(val) in (int, float) and math.isfinite(val) and val >= 0:
                result[out] = val; break
    # Currency/unit of TotalCost is not inferred. This is a provider-reported statistic.
    return result


def read_sse(response, timeout, started=None):
    """Bounded SSE assembly. [DONE] is mandatory; partial JSON is never accepted."""
    started = monotonic() if started is None else started
    text = ''; final = None; usage = {}; done = False; total = 0
    event = ''; data_lines = []; completed = False

    def dispatch(name, raw):
        nonlocal text, final, usage, done, completed
        if raw.strip() == '[DONE]':
            if name not in ('', 'done'): raise AgentError('ADP_INVALID_TERMINATOR')
            done = True; return
        try:
            frame = parse_json(raw)
        except (ValueError, TypeError): raise AgentError('ADP_INVALID_SSE_JSON') from None
        if not isinstance(frame, dict): raise AgentError('ADP_INVALID_SSE_FRAME')
        kind = frame.get('Type') or frame.get('type') or frame.get('Event') or name
        payload = frame.get('Payload', frame.get('Data', frame))
        if not isinstance(payload, dict): payload = frame
        resp = payload.get('Response', payload)
        if not isinstance(resp, dict): resp = payload
        if kind == 'error' or any(isinstance(x.get('Error'), dict) for x in (frame, payload, resp)):
            # Do not echo arbitrary provider Code/Message: they may contain request secrets.
            raise AgentError('ADP_SERVICE_ERROR')
        if kind == 'text.delta':
            if completed: raise AgentError('ADP_TEXT_AFTER_COMPLETION')
            text += _text(payload)
        elif kind == 'text.replace':
            if completed: raise AgentError('ADP_TEXT_AFTER_COMPLETION')
            text = _text(payload)
        elif kind == 'response.completed':
            if completed: raise AgentError('ADP_DUPLICATE_COMPLETION')
            completed = True
            messages = resp.get('Messages')
            if messages is not None:
                if not isinstance(messages, list): raise AgentError('ADP_INVALID_COMPLETION')
                chunks = []
                for message in messages:
                    if not isinstance(message, dict): raise AgentError('ADP_INVALID_COMPLETION')
                    contents = message.get('Contents', [])
                    if not isinstance(contents, list): raise AgentError('ADP_INVALID_COMPLETION')
                    for content in contents:
                        if isinstance(content, dict) and str(content.get('Type', '')).lower() == 'text':
                            value = content.get('Text')
                            if not isinstance(value, str): raise AgentError('ADP_INVALID_COMPLETION')
                            chunks.append(value)
                final = ''.join(chunks)
            else:
                candidate = _text(resp)
                if candidate: final = candidate
            usage = _usage(resp)
        if len(text) > MAX_RESPONSE or (final is not None and len(final) > MAX_RESPONSE):
            raise AgentError('ADP_RESPONSE_TOO_LARGE')

    while True:
        if monotonic() - started > timeout: raise AgentError('ADP_TIMEOUT')
        raw_line = response.readline(MAX_LINE + 1)
        if not raw_line: break
        total += len(raw_line)
        if total > MAX_RESPONSE or len(raw_line) > MAX_LINE: raise AgentError('ADP_RESPONSE_TOO_LARGE')
        try: line = raw_line.decode('utf-8').rstrip('\r\n')
        except UnicodeError: raise AgentError('ADP_INVALID_SSE_ENCODING') from None
        if total == len(raw_line): line = line.lstrip('\ufeff')
        if line == '':
            if data_lines: dispatch(event, '\n'.join(data_lines))
            event = ''; data_lines = []
            if done: break
        elif line.startswith('event:'): event = line[6:].strip()
        elif line.startswith('data:'): data_lines.append(line[5:].removeprefix(' '))
        # Comments, id and retry lines have no effect on the answer.
    if data_lines: dispatch(event, '\n'.join(data_lines))
    if not done: raise AgentError('ADP_INCOMPLETE_STREAM')
    # Completed output supersedes streamed drafts, never concatenates them twice.
    answer = final if final is not None else text
    answer = answer.strip().lstrip('\ufeff')
    if not answer: raise AgentError('ADP_EMPTY_RESPONSE')
    # Permit one exact Markdown JSON fence only; never salvage JSON from surrounding prose.
    match = re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n```', answer)
    if match: answer = match.group(1).strip()
    try: result = parse_json(answer)
    except (ValueError, TypeError): raise AgentError('ADP_INVALID_JUDGE_JSON') from None
    if not isinstance(result, dict): raise AgentError('ADP_INVALID_JUDGE_JSON')
    return result, {'usage': usage, 'completion_event': completed, 'terminal_event': done}


class ADPJudge:
    mode = 'tencent_adp'

    def __init__(self, config, opener=None):
        self.config = config
        self.opener = opener or build_opener(NoRedirect())
        self.last_metadata = {}

    def __call__(self, snapshot, arguments, calculations):
        self.last_metadata = {}  # Reused adapters cannot expose a previous case's trace.
        request_id, conversation_id, visitor_id = (str(uuid4()) for _ in range(3))
        body = {'RequestId': request_id, 'ConversationId': conversation_id,
                'AppKey': self.config.app_key, 'VisitorId': visitor_id,
                'Contents': [{'Type': 'text', 'Text': case_question(snapshot, arguments, calculations)}],
                'Incremental': True, 'Stream': 'enable'}
        request = Request(self.config.endpoint, data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8'),
                          headers={'Content-Type': 'application/json', 'Accept': 'text/event-stream'}, method='POST')
        started = monotonic()
        try:
            with self.opener.open(request, timeout=self.config.timeout) as response:
                content_type = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
                if content_type != 'text/event-stream': raise AgentError('ADP_UNEXPECTED_CONTENT_TYPE')
                result, metadata = read_sse(response, self.config.timeout, started)
        except HTTPError as exc:
            raise AgentError(f'ADP_HTTP_{exc.code}') from None
        except (TimeoutError, URLError, OSError):
            raise AgentError('ADP_CONNECTION_OR_TIMEOUT') from None
        # Official Ryde MVP asks for a confidence score. It is an uncalibrated model
        # self-assessment, not a measured probability. Never invent a missing score.
        score = result.get('confidence')
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise AgentError('ADP_CONFIDENCE_REQUIRED')
        self.last_metadata = {**metadata, 'request_id': request_id, 'conversation_id': conversation_id,
                              'duration_ms': round((monotonic()-started)*1000, 2),
                              'provider': 'Tencent ADP', 'model': 'configured_in_published_ADP_app'}
        return result
