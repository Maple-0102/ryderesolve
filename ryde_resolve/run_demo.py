"""Offline by default; model calls require an explicit --judge remote/adp/vertex selection."""
import argparse
import json
import sys
from pathlib import Path
from .agents import AgentError, FileAdvocate, HTTPJudge, ModelConfig
from .orchestrator import RydeOrchestrator
from .execution import CheckpointStore, RunLimits
from .adp import ADPJudge, ADPConfig
from .vertex import VertexJudge, VertexConfig
from .ui import render_html
from dataclasses import replace
from .teammate_advocate import TeammateAdvocate
from ryderesolve_evidence import EvidenceTools


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    case_ids = [row['case_id'] for row in EvidenceTools().list_cases()]
    parser.add_argument('--case', default='all', choices=['all', *case_ids])
    parser.add_argument('--judge', choices=['offline', 'remote', 'adp', 'vertex'], default='offline')
    parser.add_argument('--advocate', choices=['offline', 'teammate-vertex'], default='offline')
    parser.add_argument('--thinking-level', choices=['LOW','MEDIUM','HIGH'], help='Explicit thinking level for Vertex Judge and Advocate.')
    parser.add_argument('--advocate-file', type=Path, help='Snapshot-bound JSON with opening/response for both sides')
    parser.add_argument('--output-dir', type=Path, default=None)
    parser.add_argument('--checkpoint-dir', type=Path, help='Defaults to OUTPUT_DIR/checkpoints; contains full private case data.')
    parser.add_argument('--reviewer',choices=('none','vertex'),default='none',help='Optional extra read-only model call on validated decisive proposals.')
    parser.add_argument('--issue-guidance',action='store_true',help='Focus both response rounds on the same recorded decision conditions.')
    parser.add_argument('--resume', help='Checkpoint run UUID; requires a single --case and identical inputs/configuration.')
    parser.add_argument('--max-calls', type=int, default=7)
    parser.add_argument('--max-seconds', type=float, default=900)
    parser.add_argument('--max-recorded-tokens', type=int, default=300000)
    parser.add_argument('--transient-retries', type=int, default=1, choices=(0,1,2))
    parser.add_argument('--judge-repairs', type=int, default=1, choices=(0,1))
    args = parser.parse_args(argv)
    if args.resume and args.case == 'all': parser.error('--resume requires a single --case')
    if args.output_dir is None:
        args.output_dir = Path(__file__).resolve().parents[1] / 'outputs'
        if args.judge in ('adp', 'vertex'): args.output_dir /= args.judge + '-live'
    if args.advocate_file and args.advocate != 'offline': parser.error('--advocate-file cannot be combined with a live Advocate')
    if args.thinking_level and args.judge != 'vertex' and args.advocate != 'teammate-vertex' and args.reviewer!='vertex': parser.error('--thinking-level requires a Vertex agent')
    if args.advocate_file and args.case == 'all':
        parser.error('--advocate-file requires a single --case')
    try:
        limits = RunLimits(args.max_calls,args.max_seconds,args.max_recorded_tokens,args.transient_retries,args.judge_repairs)
        config = VertexConfig.from_env() if args.judge == 'vertex' or args.advocate == 'teammate-vertex' or args.reviewer=='vertex' else None
        if config is not None and args.thinking_level: config = replace(config, thinking_level=args.thinking_level)
        from .reviewer import InferenceReviewer
        reviewer=InferenceReviewer(VertexJudge(config)) if args.reviewer=='vertex' else None
        judge = (VertexJudge(config) if args.judge == 'vertex' else
                 ADPJudge(ADPConfig.from_env()) if args.judge == 'adp' else
                 HTTPJudge(ModelConfig.from_env()) if args.judge == 'remote' else None)
        advocate = (TeammateAdvocate(VertexJudge(config)) if args.advocate == 'teammate-vertex' else
                    FileAdvocate(args.advocate_file) if args.advocate_file else None)
    except (AgentError, ValueError, OSError) as exc:
        print(str(exc) if isinstance(exc, AgentError) else 'INVALID_ADVOCATE_FILE', file=sys.stderr)
        return 2
    cases = case_ids if args.case == 'all' else [args.case]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    store = CheckpointStore(args.checkpoint_dir or args.output_dir / 'checkpoints')
    results = []
    for case in cases:
        try:
            result = RydeOrchestrator(advocate_runner=advocate, judge_runner=judge, checkpoint_store=store,limits=limits,reviewer_runner=reviewer,issue_guidance=args.issue_guidance).run(case,resume=args.resume)
        except AgentError as exc:
            print(str(exc),file=sys.stderr);return 2
        results.append(result)
        path = args.output_dir / (result['case_id'] + '.run.json')
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        (args.output_dir / (result['case_id']+'.'+result['run_id']+'.run.json')).write_text(path.read_text(encoding='utf-8'),encoding='utf-8')
        render_html(results,args.output_dir / 'ryde-evaluation.html')
        print(f"{result['case_id']}: {result['ruling']['decision']} | {result['modes']} | errors={len(result['validation_errors'])}")
    print('UI:', render_html(results, args.output_dir / 'ryde-evaluation.html'))
    return 1 if any(r['validation_errors'] for r in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
