"""Google Cloud Gemini generateContent adapter using project-local ADC.

No API key, no tools, no automatic retry. Access tokens stay in process memory.
"""
import json
from hashlib import sha256
import math
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from ryderesolve_evidence.core import parse_json
from .agents import AgentError, NoRedirect, ROOT, build_judge_messages

MAX_RESPONSE = 2_000_000


def compact_json_context(text):
    """Remove only insignificant JSON whitespace; retain literal bytes inside strings.

    No source selection, key sorting, number rewriting, Unicode normalization or
    semantic summarization. Non-JSON prompts remain byte-for-byte unchanged.
    """
    def nonfinite(_):
        raise ValueError('nonfinite')
    try:
        json.loads(text, parse_constant=nonfinite)
    except (ValueError, TypeError):
        return text
    output=[];quoted=False;escaped=False
    for char in text:
        if quoted:
            output.append(char)
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='"':
            quoted=True;output.append(char)
        elif char not in ' \t\r\n':output.append(char)
    return ''.join(output)


@dataclass(frozen=True)
class VertexConfig:
    project: str
    model: str = 'gemini-3.8-flash'
    location: str = 'global'
    timeout: float = 120.0
    thinking_level: str | None = None
    compact_context: bool = False

    def __post_init__(self):
        if type(self.compact_context) is not bool:
            raise AgentError('VERTEX_INVALID_COMPACT_CONTEXT')
        for value, pattern in ((self.project, r'[a-z][a-z0-9-]{4,62}'),
                               (self.model, r'gemini-[a-zA-Z0-9.-]{1,100}'),
                               (self.location, r'global|[a-z]+-[a-z]+[0-9]')):
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise AgentError('VERTEX_INVALID_CONFIG')
        if not math.isfinite(self.timeout) or not 0 < self.timeout <= 300:
            raise AgentError('VERTEX_INVALID_TIMEOUT')
        if self.thinking_level is not None and (self.thinking_level not in {'LOW', 'MEDIUM', 'HIGH'} or not self.model.startswith('gemini-3')):
            raise AgentError('VERTEX_INVALID_THINKING_LEVEL')

    @property
    def endpoint(self):
        host = 'aiplatform.googleapis.com' if self.location == 'global' else self.location + '-aiplatform.googleapis.com'
        return (f'https://{host}/v1/projects/{self.project}/locations/{self.location}'
                f'/publishers/google/models/{self.model}:generateContent')

    @classmethod
    def from_env(cls):
        try:
            config = json.loads((ROOT / '.local/vertex-config.json').read_text())
        except FileNotFoundError:
            config = {}
        except (ValueError, OSError):
            raise AgentError('VERTEX_INVALID_CONFIG') from None
        if not isinstance(config, dict): raise AgentError('VERTEX_INVALID_CONFIG')
        try:
            return cls(os.environ.get('RYDE_VERTEX_PROJECT', config.get('project', '')),
                       os.environ.get('RYDE_VERTEX_MODEL', config.get('model', 'gemini-3.8-flash')),
                       os.environ.get('RYDE_VERTEX_LOCATION', config.get('location', 'global')),
                       float(os.environ.get('RYDE_VERTEX_TIMEOUT', '120')),
                       os.environ.get('RYDE_VERTEX_THINKING_LEVEL', config.get('thinking_level')),
                       config.get('compact_context',False))
        except (TypeError, ValueError):
            raise AgentError('VERTEX_INVALID_CONFIG') from None


def adc_token(config):
    directory = ROOT / '.local/gcloud'
    credential = directory / 'application_default_credentials.json'
    try:
        mode = credential.stat().st_mode
        if credential.is_symlink() or not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            raise AgentError('VERTEX_ADC_UNSAFE_FILE')
        doc = json.loads(credential.read_text())
        if doc.get('quota_project_id') != config.project:
            raise AgentError('VERTEX_ADC_QUOTA_PROJECT_MISMATCH')
    except (OSError, ValueError, AttributeError):
        raise AgentError('VERTEX_ADC_MISSING_OR_INVALID') from None
    env = os.environ.copy()
    for name in ('GOOGLE_APPLICATION_CREDENTIALS', 'CLOUDSDK_AUTH_ACCESS_TOKEN', 'CLOUDSDK_AUTH_ACCESS_TOKEN_FILE'):
        env.pop(name, None)
    env.update(CLOUDSDK_CONFIG=str(directory), CLOUDSDK_PYTHON=sys.executable,
               CLOUDSDK_CORE_DISABLE_USAGE_REPORTING='true')
    try:
        proc = subprocess.run([str(ROOT / '.local/google-cloud-sdk/bin/gcloud'),
                               'auth', 'application-default', 'print-access-token', '--quiet', '--verbosity=none'],
                              env=env, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise AgentError('VERTEX_ADC_REFRESH_FAILED') from None
    token = proc.stdout.strip()
    if proc.returncode or not token or any(c.isspace() for c in token):
        raise AgentError('VERTEX_ADC_REFRESH_FAILED')
    return token


class VertexJudge:
    mode = 'google_vertex'

    def __init__(self, config, opener=None, token_provider=None):
        self.config = config
        self.opener = opener or build_opener(NoRedirect())
        self.token_provider = token_provider or adc_token
        self.last_metadata = {}

    def __call__(self, snapshot, arguments, calculations):
        messages = build_judge_messages(snapshot, arguments, calculations)
        from .output_schema import judge_output_schema, vertex_response_schema
        from .policy_v21 import bound
        result = self.generate(messages[0]['content'], messages[1]['content'],
                               response_schema=vertex_response_schema(judge_output_schema(policy_bound=bound(snapshot), arguments=arguments, snapshot=snapshot)))
        value = result.get('confidence')
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise AgentError('VERTEX_CONFIDENCE_REQUIRED')
        return result

    def repair(self, snapshot, arguments, calculations, previous, errors):
        """One bounded structural correction; the orchestrator rechecks every invariant."""
        messages = build_judge_messages(snapshot, arguments, calculations)
        context = json.loads(messages[1]['content'])
        context['structural_repair'] = {'previous_proposal': previous, 'validation_errors': errors,
            'instruction': 'Repair only missing structure or argument coverage using this same case. Preserve the business decision and amount if a prior proposal exists. Do not change evidence, policy, resolve flags or invent references. Return the entire corrected object.'}
        from .output_schema import judge_output_schema, vertex_response_schema
        from .policy_v21 import bound
        return self.generate(messages[0]['content'], json.dumps(context,ensure_ascii=False,allow_nan=False),
            response_schema=vertex_response_schema(judge_output_schema(policy_bound=bound(snapshot),arguments=arguments,snapshot=snapshot)))

    def generate(self, system, user, max_output_tokens=16384, *, response_schema=None):
        self.last_metadata = {}
        started = monotonic()
        original_user = user
        if self.config.compact_context: user = compact_json_context(user)
        context_bytes = {'input':len(original_user.encode('utf-8')),'sent':len(user.encode('utf-8'))}
        body = {'systemInstruction': {'parts': [{'text': system}]},
                'contents': [{'role': 'user', 'parts': [{'text': user}]}],
                'generationConfig': {'responseMimeType': 'application/json',
                                     'candidateCount': 1, 'maxOutputTokens': max_output_tokens}}
        schema_hash = None
        if response_schema is not None:
            body['generationConfig']['responseSchema'] = response_schema
            schema_hash = sha256(json.dumps(response_schema, sort_keys=True).encode()).hexdigest()
        if self.config.thinking_level is not None:
            body['generationConfig']['thinkingConfig'] = {'thinkingLevel': self.config.thinking_level}
        token = self.token_provider(self.config)
        req = Request(self.config.endpoint, data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode(),
                      headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token,
                               'X-Goog-User-Project': self.config.project}, method='POST')
        try:
            with self.opener.open(req, timeout=self.config.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE: raise AgentError('VERTEX_RESPONSE_TOO_LARGE')
        except HTTPError as exc:
            raise AgentError(f'VERTEX_HTTP_{exc.code}') from None
        except (OSError, URLError, TimeoutError):
            raise AgentError('VERTEX_CONNECTION_OR_TIMEOUT') from None
        try:
            obj = parse_json(raw)
            if obj.get('promptFeedback', {}).get('blockReason'): raise AgentError('VERTEX_BLOCKED')
            candidates = obj['candidates']
            if len(candidates) != 1: raise AgentError('VERTEX_INVALID_CANDIDATES')
            candidate = candidates[0]
            usage = {k: v for k, v in obj.get('usageMetadata', {}).items()
                     if k.endswith('TokenCount') and type(v) is int and v >= 0}
            reported_model = obj.get('modelVersion')
            self.last_metadata = {'provider': 'google_cloud', 'requested_model': self.config.model,
                                  'reported_model': reported_model if isinstance(reported_model, str) else None,
                                  'location': self.config.location, 'thinking_level': self.config.thinking_level or 'provider_default',
                                  'max_output_tokens': max_output_tokens, 'usage': usage,
                                  'response_schema_sha256': schema_hash,
                                  'compact_context_requested': self.config.compact_context,
                                  'context_encoding': 'minified_json' if user!=original_user else 'original',
                                  'context_bytes': context_bytes,
                                  'duration_ms': round((monotonic() - started) * 1000, 2)}
            reason = candidate.get('finishReason')
            self.last_metadata['finish_reason'] = reason if isinstance(reason, str) and re.fullmatch(r'[A-Z_]{1,64}', reason) else 'UNKNOWN'
            if reason != 'STOP': raise AgentError('VERTEX_INCOMPLETE_RESPONSE_' + self.last_metadata['finish_reason'])
            parts = candidate['content']['parts']
            if any('functionCall' in part for part in parts): raise AgentError('VERTEX_UNEXPECTED_TOOL_CALL')
            text = ''.join(p['text'] for p in parts if not p.get('thought') and isinstance(p.get('text'), str))
            result = parse_json(text)
            if not isinstance(result, dict): raise AgentError('VERTEX_INVALID_JSON_OBJECT')
            return result
        except AgentError:
            raise
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            raise AgentError('VERTEX_INVALID_RESPONSE') from None
