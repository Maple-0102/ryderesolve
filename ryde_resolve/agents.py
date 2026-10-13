"""Integration ports for teammate JSON outputs and a configurable model-backed Judge."""
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ryderesolve_evidence.core import parse_json, read_json

ROOT = Path(__file__).resolve().parents[1]


class AgentError(RuntimeError):
    """Safe error code; do not include credentials, endpoints or remote response bodies."""


class FileAdvocate:
    mode = 'teammate_json'

    def __init__(self, path):
        self.document = read_json(Path(path))

    def __call__(self, snapshot, side, round_name, opponent=None):
        doc = self.document
        if not isinstance(doc, dict) or doc.get('snapshot_id') != snapshot['snapshot_id']:
            raise AgentError('ADVOCATE_SNAPSHOT_MISMATCH')
        if doc.get('case_id') != snapshot['case_id']:
            raise AgentError('ADVOCATE_CASE_MISMATCH')
        try:
            return doc[round_name][side]
        except (KeyError, TypeError):
            raise AgentError('ADVOCATE_ROUND_MISSING') from None


@dataclass(frozen=True)
class ModelConfig:
    endpoint: str
    model: str
    api_key: str = field(repr=False)
    timeout: float = 45.0

    def __post_init__(self):
        u = urlsplit(self.endpoint)
        if (not u.hostname or u.username or u.password or u.query or u.fragment
                or (u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in
                                                {'127.0.0.1', 'localhost', '::1'}))):
            raise AgentError('INVALID_MODEL_ENDPOINT')
        if not self.model.strip() or not self.api_key.strip():
            raise AgentError('MODEL_CONFIG_MISSING')
        if not math.isfinite(self.timeout) or not 0 < self.timeout <= 120:
            raise AgentError('INVALID_MODEL_TIMEOUT')

    @classmethod
    def from_env(cls):
        values = [os.environ.get(k, '') for k in
                  ('RYDE_JUDGE_ENDPOINT', 'RYDE_JUDGE_MODEL', 'RYDE_JUDGE_API_KEY')]
        if not all(values):
            raise AgentError('MODEL_CONFIG_MISSING: set RYDE_JUDGE_ENDPOINT, RYDE_JUDGE_MODEL, RYDE_JUDGE_API_KEY')
        try:
            timeout = float(os.environ.get('RYDE_JUDGE_TIMEOUT', '45'))
        except ValueError:
            raise AgentError('INVALID_MODEL_TIMEOUT') from None
        return cls(*values, timeout=timeout)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the bearer token to a redirected destination.
        return None


def build_judge_messages(snapshot, arguments, calculations):
    prompt = (ROOT / 'prompts/judge_prompt.md').read_text(encoding='utf-8')
    payload = {k: snapshot[k] for k in ('case_id', 'snapshot_id', 'raw', 'evidence_pack', 'audit', 'source_index')}
    payload.update(arguments=arguments, calculations=calculations)
    return [{'role': 'system', 'content': prompt},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, allow_nan=False)}]


class HTTPJudge:
    mode = 'remote_llm'

    def __init__(self, config, opener=None):
        self.config = config
        self.opener = opener or build_opener(NoRedirect())

    def __call__(self, snapshot, arguments, calculations):
        request_body = {'model': self.config.model, 'messages': build_judge_messages(snapshot, arguments, calculations),
                        'stream': False, 'response_format': {'type': 'json_object'}, 'max_tokens': 6000}
        request = Request(self.config.endpoint,
                          data=json.dumps(request_body, ensure_ascii=False, allow_nan=False).encode(),
                          headers={'Content-Type': 'application/json',
                                   'Authorization': 'Bearer ' + self.config.api_key}, method='POST')
        try:
            with self.opener.open(request, timeout=self.config.timeout) as response:
                body = response.read(1_000_001)
            if len(body) > 1_000_000:
                raise AgentError('MODEL_RESPONSE_TOO_LARGE')
        except HTTPError as exc:
            raise AgentError(f'MODEL_HTTP_{exc.code}') from None
        except (TimeoutError, URLError, OSError):
            raise AgentError('MODEL_CONNECTION_OR_TIMEOUT') from None
        try:
            obj = parse_json(body)
            choice = obj['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise AgentError('MODEL_INCOMPLETE_RESPONSE')
            content = choice['message']['content']
            if not isinstance(content, str) or not content.strip():
                raise AgentError('MODEL_EMPTY_RESPONSE')
            result = parse_json(content)
            if not isinstance(result, dict):
                raise AgentError('MODEL_INVALID_JSON_OBJECT')
            return result
        except AgentError:
            raise
        except (KeyError, IndexError, TypeError, ValueError):
            raise AgentError('MODEL_INVALID_RESPONSE') from None
