"""Judge-only evaluation. Offline by default; no real Advocate needed."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from datetime import datetime, timezone
from ryde_resolve.agents import AgentError, HTTPJudge, ModelConfig, build_judge_messages
from ryde_resolve.contracts import check_judge, check_advocate
from ryde_resolve.evidence import verify_snapshot, validate_snapshot_output
from ryde_resolve.mock_agents import OfflineJudge
from ryde_resolve.adp import ADPJudge, ADPConfig, case_question
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.vertex import VertexJudge, VertexConfig
from .judge_suite import build_exercises
from .metrics import summarize_metrics
from hashlib import sha256
from copy import deepcopy
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[1]


def safe_rejected_output(output):
    try:
        json.dumps(output, allow_nan=False)
        return output
    except (ValueError, TypeError, OverflowError):
        return {'omitted': 'rejected non-JSON model output'}


def evaluate(judge, exercises, on_result=None):
    rows = []
    for exercise in exercises:
        s = exercise['snapshot']; args = exercise['arguments']; verify_snapshot(s)
        for rnd in args.values():
            for side, out in rnd.items():
                if check_advocate(s, out, side)[0]: raise ValueError('Invalid exercise Advocate input')
        calc = calculate_rules(s)
        # Expected answers, exercise IDs and scoring instructions NEVER go into this payload.
        input_text = (case_question(s, args, calc) if getattr(judge, 'mode', '') == 'tencent_adp'
                      else json.dumps(build_judge_messages(s, args, calc), ensure_ascii=False))
        input_hash = sha256(input_text.encode()).hexdigest()
        start = perf_counter(); output = None; errors = []; warnings = []; shared_pass = False
        try:
            output = judge(deepcopy(s), deepcopy(args), deepcopy(calc))
            shared = validate_snapshot_output(s, judge=output)
            shared_pass = not shared['errors']
            errors, warnings = check_judge(s, output, args)
        except Exception as exc:
            errors = [str(exc) if isinstance(exc, AgentError) else 'EVALUATION_CALL_FAILED_' + type(exc).__name__]
        if not errors and (not isinstance(output, dict) or not isinstance(output.get('case_analysis'), dict)):
            errors.append('EVALUATION_REQUIRES_STRUCTURED_ANALYSIS')
        valid = not errors
        expected = exercise['expected']
        decision = output.get('decision') if isinstance(output, dict) else None
        amount = output.get('refund_amount') if isinstance(output, dict) else None
        matches = valid and decision == expected['decision'] and amount == expected['refund_amount']
        # Invalid model decisions are failures, even if the production gate would turn them into review.
        rows.append({'exercise_id': exercise['exercise_id'], 'purpose': exercise['purpose'],
                     'input_sha256': input_hash, 'snapshot_id': s['snapshot_id'],
                     'prompt_sha256': sha256((ROOT / 'prompts/judge_prompt.md').read_bytes()).hexdigest(),
                     'expected': expected, 'model_decision': decision if isinstance(decision, str) else None,
                     'effective_decision': decision if valid else 'escalate',
                     'shared_contract_pass': shared_pass,
                     'all_checks_pass': valid, 'behaviour_match': matches,
                     'accepted_output': output if valid else None,
                     'transport': deepcopy(judge.last_metadata) if isinstance(judge, (ADPJudge, VertexJudge)) else {},
                     'errors': errors, 'warnings': warnings, 'duration_ms': round((perf_counter()-start)*1000,2),
                     'order_pair': exercise['order_pair'], 'split': exercise.get('split', 'development'),
                     'data_origin': s['audit'].get('data_origin'), 'policy_origin': s['audit'].get('policy_origin'),
                     'policy_provenance_sha256': calc['policy_provenance']['sha256'],
                     'rejected_output': safe_rejected_output(output) if not valid else None})
        if on_result: on_result(deepcopy(rows))
    review = [r for r in rows if r['expected']['decision'] == 'escalate']
    decisive = [r for r in rows if r['expected']['decision'] != 'escalate']
    pairs = {}
    for r in rows:
        if r['order_pair']: pairs.setdefault(r['order_pair'], []).append(r)
    pair_results = {key: {'comparable': len(group) == 2 and all(r['all_checks_pass'] for r in group),
                          'same_decision': len(group) == 2 and all(r['all_checks_pass'] for r in group) and len({r['model_decision'] for r in group}) == 1,
                          'both_correct': len(group) == 2 and all(r['behaviour_match'] for r in group)}
                    for key, group in pairs.items()}
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'mode': getattr(judge, 'mode', 'custom_test_runner'),
            'model_quality_measured': getattr(judge, 'mode', None) in {'remote_llm', 'tencent_adp', 'google_vertex'} and any(r['all_checks_pass'] for r in rows),
            'metrics': summarize_metrics(rows),
            'limitations': 'Small synthetic exercise set; behaviour matching is not real-world accuracy or fairness. Offline scores test the harness only.',
            'summary': {'total': len(rows), 'all_checks_pass': sum(r['all_checks_pass'] for r in rows),
                        'required_review': {'matched': sum(r['behaviour_match'] for r in review), 'total': len(review)},
                        'resolvable_cases': {'matched': sum(r['behaviour_match'] for r in decisive), 'total': len(decisive)},
                        'order_pairs': pair_results}, 'results': rows}


def render_report(report):
    def cell(value): return str(value).replace('|', '/').replace('\n', ' ')
    summary = report['summary']
    lines = ['# Judge 独立考题结果', '', f"运行模式：{cell(report['mode'])}。",
             '离线结果仅用于检查评分程序，不能当作真实模型准确率。考题包含人工编写的论点与明确标注的合成变体。', '',
             f"结构及校验通过：{summary['all_checks_pass']}/{summary['total']}。",
             f"应当复核的考题：{summary['required_review']['matched']}/{summary['required_review']['total']} 符合预期。",
             f"可明确裁决的考题：{summary['resolvable_cases']['matched']}/{summary['resolvable_cases']['total']} 符合预期。", '',
             '| 考题 | 预期行为 | 实际输出 | 校验及分析完整 | 行为符合预期 |', '|---|---|---|---|---|']
    for row in report['results']:
        lines.append('| ' + ' | '.join(cell(x) for x in [row['exercise_id'], row['expected']['decision'],
                     row['model_decision'], '通过' if row['all_checks_pass'] else '未通过',
                     '是' if row['behaviour_match'] else '否']) + ' |')
    lines += ['', '顺序对照同时记录“结论相同”和“两次都正确”；永远转人工虽然结论相同，也不能得正确性分。',
              '预期答案仅供评分使用，不进入 Judge 的请求。校验拒绝后自动转人工，也不计为模型正确回答。',
              '原始 JSON 报告包含输入哈希、有效及被拒绝输出、错误码、耗时和记录到的 token 用量。小规模考题不能证明真实业务准确率、公平性或提示注入防御效果。', '']
    if 'metrics' in report:
        m = report['metrics']
        lines += ['## 按预期裁决分类', '', '| 类别 | 符合预期 / 总数 |', '|---|---|']
        for decision, score in m['by_expected_decision'].items():
            lines.append(f"| {decision} | {score['matched']}/{score['total']} |")
        lines += ['', f"无效输出：{m['invalid_outputs']}；应裁决却转人工：{m['false_escalations']}；应复核却明确裁决：{m['unsafe_decisive_recommendations']}。",
                  f"耗时中位数：{m['latency_ms']['median']} ms；小样本 p95：{m['latency_ms']['p95_sample']} ms。",
                  '完整退款场景若为 0/0，表示未覆盖，不是通过。留出候选题共享同一案例家族，不是独立业务数据。', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--judge', choices=['offline', 'remote', 'adp', 'vertex'], default='offline')
    parser.add_argument('--exercise', action='append', help='Exercise ID; repeat to select several within the chosen suite.')
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--thinking-level', choices=['LOW', 'MEDIUM', 'HIGH'], help='Explicit Gemini 3 thinking level; vertex only.')
    parser.add_argument('--suite', choices=['development', 'holdout', 'all'], default='development')
    args = parser.parse_args(argv)
    if args.thinking_level and args.judge != 'vertex': parser.error('--thinking-level requires --judge vertex')
    if args.output is None:
        args.output = ROOT / 'outputs' / ('judge-evaluation-' + args.judge + '.json')
    exercises = build_exercises(args.suite)
    if args.exercise:
        unknown = set(args.exercise) - {x['exercise_id'] for x in exercises}
        if unknown: parser.error('Unknown exercise: ' + ', '.join(sorted(unknown)))
        exercises = [x for x in exercises if x['exercise_id'] in args.exercise]
    try:
        judge = (VertexJudge(replace(VertexConfig.from_env(), thinking_level=args.thinking_level) if args.thinking_level else VertexConfig.from_env()) if args.judge == 'vertex' else
                 ADPJudge(ADPConfig.from_env()) if args.judge == 'adp' else
                 HTTPJudge(ModelConfig.from_env()) if args.judge == 'remote' else OfflineJudge())
    except AgentError as exc:
        parser.exit(2, str(exc) + '\n')
    def checkpoint(rows):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        partial = {'status': 'in_progress', 'mode': getattr(judge, 'mode', None),
                   'suite': args.suite, 'planned_total': len(exercises), 'completed': len(rows),
                   'prompt_sha256': sha256((ROOT / 'prompts/judge_prompt.md').read_bytes()).hexdigest(),
                   'results': rows}
        args.output.with_suffix('.partial.json').write_text(json.dumps(partial, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        print(json.dumps({'completed': len(rows), 'total': len(exercises),
                          'exercise': rows[-1]['exercise_id'], 'matched': rows[-1]['behaviour_match'],
                          'errors': rows[-1]['errors'], 'duration_ms': rows[-1]['duration_ms']}, ensure_ascii=False), flush=True)
    report = evaluate(judge, exercises, on_result=checkpoint)
    report.update(status='complete', suite=args.suite, thinking_level=(judge.config.thinking_level or 'provider_default') if args.judge == 'vertex' else None)
    report['analysis_schema_sha256'] = sha256((ROOT / 'schemas/judge-analysis.schema.json').read_bytes()).hexdigest()
    report['model'] = (judge.config.model if args.judge in ('remote', 'vertex') else
                       'configured_in_published_ADP_app' if args.judge == 'adp' else None)
    report['prompt_sha256'] = sha256((ROOT / 'prompts/judge_prompt.md').read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    args.output.with_suffix('.md').write_text(render_report(report), encoding='utf-8')
    print(json.dumps({'mode': report['mode'], 'summary': report['summary'], 'report': str(args.output)}, ensure_ascii=False, indent=2))
    return 0 if all(r['behaviour_match'] for r in report['results']) else 1


if __name__ == '__main__': raise SystemExit(main())
