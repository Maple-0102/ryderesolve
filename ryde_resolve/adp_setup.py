"""Prepare ADP console materials or save an AppKey locally without echoing it."""
import argparse
import getpass
import json
import os
import tempfile
from pathlib import Path
from hashlib import sha256
from .adp import ADPConfig, KEY_FILE, case_question
from .agents import AgentError, ROOT
from .evidence import EvidenceGateway
from .mock_agents import OfflineAdvocate
from .rule_engine import calculate_rules


def save_key(key, path=KEY_FILE):
    # Reject accidental pasted JSON, whitespace and empty strings before touching disk.
    ADPConfig(key)
    path = Path(path)
    if path.parent.is_symlink() or path.is_symlink(): raise AgentError('ADP_KEY_FILE_UNSAFE')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.adp-key-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(key + '\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def prepare_console(directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    prompt = (ROOT / 'prompts/judge_prompt.md').read_text(encoding='utf-8')
    (directory / 'judge-system-prompt.txt').write_text(prompt, encoding='utf-8')
    s = EvidenceGateway().prepare('DISP-002'); advocate = OfflineAdvocate()
    args = {rnd: {side: advocate(s, side, rnd) for side in ('rider','driver')} for rnd in ('opening','response')}
    question = case_question(s, args, calculate_rules(s))
    (directory / 'judge-debug-input.txt').write_text(question, encoding='utf-8')
    (directory / 'setup-manifest.json').write_text(json.dumps({
        'app_name': 'RydeResolve-Judge', 'case_id': s['case_id'], 'snapshot_id': s['snapshot_id'],
        'prompt_sha256': sha256(prompt.encode()).hexdigest(), 'input_sha256': sha256(question.encode()).hexdigest(),
        'input_origin': 'organizer sample plus offline placeholder arguments; no real Advocate output',
        'cloud_status': 'not_configured_by_this_command',
        'required_output': 'Judge JSON including confidence; uncalibrated model self-assessment',
    }, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return directory


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true', help='Write console prompt/debug input only; never ask for a key or call the cloud')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/adp-setup')
    args=parser.parse_args(argv)
    directory = prepare_console(args.output_dir)
    print('ADP console materials:', directory)
    if args.prepare_only: return 0
    try:
        key = getpass.getpass('Paste the published ADP AppKey (hidden; Enter to cancel): ').strip()
        if not key:
            print('No key saved.'); return 1
        save_key(key)
    except (AgentError, OSError, EOFError, KeyboardInterrupt) as exc:
        print(str(exc) if isinstance(exc, AgentError) else 'ADP_KEY_SETUP_CANCELLED_OR_FAILED')
        return 2
    print('AppKey saved locally with restricted permissions. It was not printed or sent to a server.')
    print('Next: .venv/bin/python -m evaluation.run_judge_suite --judge adp --exercise NS-CLOCK')
    return 0


if __name__ == '__main__': raise SystemExit(main())
