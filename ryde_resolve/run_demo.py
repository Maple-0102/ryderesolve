"""Offline by default; model calls require an explicit --judge remote/adp/vertex selection."""
import argparse
import json
import sys
from pathlib import Path
from .agents import AgentError, FileAdvocate, HTTPJudge, ModelConfig
from .orchestrator import RydeOrchestrator
from .adp import ADPJudge, ADPConfig
from .vertex import VertexJudge, VertexConfig
from .ui import render_html
from dataclasses import replace
from .teammate_advocate import TeammateAdvocate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', default='all', choices=['all', 'DISP-002', 'SYN-ROUTE-001'])
    parser.add_argument('--judge', choices=['offline', 'remote', 'adp', 'vertex'], default='offline')
    parser.add_argument('--advocate', choices=['offline', 'teammate-vertex'], default='offline')
    parser.add_argument('--thinking-level', choices=['LOW','MEDIUM','HIGH'], help='Explicit thinking level for Vertex Judge and Advocate.')
    parser.add_argument('--advocate-file', type=Path, help='Snapshot-bound JSON with opening/response for both sides')
    parser.add_argument('--output-dir', type=Path, default=None)
    args = parser.parse_args(argv)
    if args.output_dir is None:
        args.output_dir = Path(__file__).resolve().parents[1] / 'outputs'
        if args.judge in ('adp', 'vertex'): args.output_dir /= args.judge + '-live'
    if args.advocate_file and args.advocate != 'offline': parser.error('--advocate-file cannot be combined with a live Advocate')
    if args.thinking_level and args.judge != 'vertex' and args.advocate != 'teammate-vertex': parser.error('--thinking-level requires a Vertex agent')
    if args.advocate_file and args.case == 'all':
        parser.error('--advocate-file requires a single --case')
    try:
        config = VertexConfig.from_env() if args.judge == 'vertex' or args.advocate == 'teammate-vertex' else None
        if config is not None and args.thinking_level: config = replace(config, thinking_level=args.thinking_level)
        judge = (VertexJudge(config) if args.judge == 'vertex' else
                 ADPJudge(ADPConfig.from_env()) if args.judge == 'adp' else
                 HTTPJudge(ModelConfig.from_env()) if args.judge == 'remote' else None)
        advocate = (TeammateAdvocate(VertexJudge(config)) if args.advocate == 'teammate-vertex' else
                    FileAdvocate(args.advocate_file) if args.advocate_file else None)
    except (AgentError, ValueError, OSError) as exc:
        print(str(exc) if isinstance(exc, AgentError) else 'INVALID_ADVOCATE_FILE', file=sys.stderr)
        return 2
    cases = ['DISP-002', 'SYN-ROUTE-001'] if args.case == 'all' else [args.case]
    results = [RydeOrchestrator(advocate_runner=advocate, judge_runner=judge).run(case) for case in cases]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        path = args.output_dir / (result['case_id'] + '.run.json')
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        print(f"{result['case_id']}: {result['ruling']['decision']} | {result['modes']} | errors={len(result['validation_errors'])}")
    print('UI:', render_html(results, args.output_dir / 'ryde-evaluation.html'))
    return 1 if any(r['validation_errors'] for r in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
