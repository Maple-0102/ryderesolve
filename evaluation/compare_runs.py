"""Compare development runs without pooling repaired/tuned results into a holdout score."""
import argparse
import json
from pathlib import Path


def compare_reports(paths):
    rows = []
    for path in paths:
        report = json.loads(Path(path).read_text())
        scores = report['results']
        rows.append({'report': str(path), 'prompt_sha256': report['prompt_sha256'],
                     'total': len(scores), 'strict_matches': sum(r['behaviour_match'] for r in scores),
                     'direction_agreement_before_validation': sum(r['model_decision'] == r['expected']['decision'] for r in scores),
                     'invalid_outputs': sum(not r['all_checks_pass'] for r in scores),
                     'by_expected_decision': report['metrics']['by_expected_decision'],
                     'recorded_token_usage': report['metrics']['recorded_token_usage']})
    return {'runs': rows, 'boundary': 'Direction agreement ignores validation and amount; it is diagnostic, not a pass score. Development prompts were refined using these cases; never pool runs or report these as independent test accuracy.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports', nargs='+', type=Path); p.add_argument('--output', required=True, type=Path)
    args = p.parse_args(); result = compare_reports(args.reports)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
