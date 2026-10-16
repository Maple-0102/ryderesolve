"""Verify retained sources, copied runs and static recording files, without models."""
from hashlib import sha256
from pathlib import Path
import argparse
import json


def checked_path(root, relative):
    if not isinstance(relative,str) or Path(relative).is_absolute():
        raise ValueError('Relative artifact path required')
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Artifact path escapes its directory')
    return path


def verify(directory):
    directory=Path(directory).resolve()
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest.get('kind')!='static recording package' or manifest.get('opening_provider_calls')!=0:
        raise ValueError('Unexpected recording manifest')
    if not manifest.get('files') or not manifest.get('source_reports'):
        raise ValueError('Recording package has no verification hashes; rebuild it first')
    for relative,expected in manifest['files'].items():
        if sha256(checked_path(directory,relative).read_bytes()).hexdigest()!=expected:
            raise ValueError('Recording file hash mismatch: '+relative)
    source_rows={};usage=0
    for reference in manifest['source_reports']:
        # Sources may be siblings of the package but must stay under its parent.
        path=checked_path(directory.parent,str(Path(directory.name)/reference['path']))
        if sha256(path.read_bytes()).hexdigest()!=reference['sha256']:
            raise ValueError('Source report hash mismatch')
        report=json.loads(path.read_text())
        if not (report['kind'].startswith('fresh ') or report['kind'].startswith('offline revalidation')):
            raise ValueError('Unexpected source report type')
        usage+=report['summary']['provider_calls']
        for row in report['results']:
            key=row['exercise_id']
            if key in source_rows:raise ValueError('Duplicate exercise in source reports')
            source_rows[key]=(reference['sha256'],report,row)
    entries=manifest['entries']
    keys=[entry['exercise_id'] for entry in entries]
    if len(keys)!=len(set(keys)) or set(keys)!=set(source_rows):
        raise ValueError('Exercise coverage mismatch; failed cases must be retained')
    runs=[]
    for entry in entries:
        digest,report,row=source_rows[entry['exercise_id']]
        for field in ('html','run_json'):
            if entry[field] not in manifest['files']:raise ValueError('Unhashed recording artifact')
        run=json.loads(checked_path(directory,entry['run_json']).read_text())
        if run!=row['run']:raise ValueError('Copied run differs from source report')
        expected={'origin':run['snapshot']['audit']['data_origin'],
                  'replayed':report['kind'].startswith('offline revalidation'),
                  'source_sha256':digest,'runtime_implementation':report['runtime_implementation'],
                  'validation_errors':run['validation_errors'],'first_pass_valid':run.get('first_pass_valid'),
                  'adjustments':len(run.get('judge_adjustments',[])),
                  'decision':run['ruling']['decision'],'refund_amount':run['ruling']['refund_amount']}
        if any(entry.get(k)!=v for k,v in expected.items()):
            raise ValueError('Manifest result differs from source report')
        runs.append(run)
    return {'kind':'offline recording integrity verification','verified':True,'verification_provider_calls':0,
            'cases':len(runs),'source_recorded_provider_calls':usage,
            'final_formal_acceptance':sum(not r['validation_errors'] for r in runs),
            'raw_first_pass_acceptance':sum(r.get('first_pass_valid') is True for r in runs),
            'runs_with_program_adjustments':sum(bool(r.get('judge_adjustments')) for r in runs),
            'retained_failures':sum(bool(r['validation_errors']) for r in runs),
            'boundary':'File and record consistency only. No new model run, semantic proof, authenticity signature or accuracy estimate.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(args.directory),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
