"""Export reproducible model inputs separately from scorer-only answer labels."""
import argparse
import json
from hashlib import sha256
from pathlib import Path
from ryde_resolve.agents import build_judge_messages
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.evidence import verify_snapshot
from .judge_suite import build_exercises


def export_dataset(directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    labels = {}; manifest = []
    for i, x in enumerate(build_exercises('all'), 1):
        # Opaque filenames: purpose, expected answer, and exercise name never enter model input.
        name = f'input-{i:03d}.json'
        s = x['snapshot']; verify_snapshot(s)
        payload = build_judge_messages(s, x['arguments'], calculate_rules(s))
        text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        (directory/name).write_text(text, encoding='utf-8')
        labels[name] = {'exercise_id': x['exercise_id'], 'expected': x['expected'],
                        'purpose': x['purpose'], 'split': x['split'], 'label_basis': x['label_basis']}
        manifest.append({'file': name, 'sha256': sha256(text.encode()).hexdigest(),
                         'snapshot_id': s['snapshot_id'], 'split': x['split'],
                         'data_origin': s['audit'].get('data_origin'), 'policy_origin': s['audit'].get('policy_origin')})
    for name, value in [('manifest.json', {'version': '0.8', 'total': len(manifest), 'cases': manifest,
             'limitations': 'Two seed cases only. Holdout candidates share a seed family; no independent or real-world accuracy claim. Labels are team expectations, never official answers.'}),
                         ('scorer-only-labels.json', labels)]:
        (directory/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (directory/'README.md').write_text(
        '# Judge 模拟测试包\n\n9 个开发题 + 6 个尚未用真实模型运行的留出候选题，源自两个案例家族。\n'
        '输入文件为直接可调用的消息，不含评分答案。scorer-only-labels.json 只供评分，禁止发送给模型。\n'
        '留出题与开发题共享路线种子，因此不是独立业务样本。第一次运行后记录其已被使用；调参后不能继续声称未见过。\n'
        '金额变体、核实记录和预期裁决均为人工定义的模拟测试，不是 Ryde 官方政策或标准答案。\n', encoding='utf-8')
    return len(manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('outputs/judge-dataset-v0.8'))
    args = parser.parse_args(); print(f'Exported {export_dataset(args.output)} cases to {args.output}')


if __name__ == '__main__': main()
