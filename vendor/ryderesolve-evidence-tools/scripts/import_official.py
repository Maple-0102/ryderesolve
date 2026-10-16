"""Import the four organizer attachments; keep originals outside the runtime wheel.

Usage: python scripts/import_official.py --source-dir <attachment directory>
No network calls. Projection exclusions are explicit and recorded in the manifest.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'DISP-001': 'RydeResolve Route Deviation Dataset — DISP-001.md',
    'DISP-002': 'RydeResolve Sample Dataset — DISP-002 No-Show Charge Dispute (SG)(1).md',
    'DISP-003': 'Document 1 — Fare Dispute Sample Data (JSON).md',
    'policy': 'Document 2 — Ryde Dispute Resolution Policy v2.1 (Markdown).md',
}
EXCLUDED = [
    '/case_metadata', '/chat_log_analysis', '/traffic_analysis',
    '/evidence_summary', '/recommended_ruling', '/fare_breakdown/notes',
    '/traffic_conditions/2/description',
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def project_route(raw):
    projected = copy.deepcopy(raw)
    for ref in EXCLUDED:
        tokens = ref.strip('/').split('/')
        parent = projected
        for token in tokens[:-1]:
            parent = parent[int(token)] if isinstance(parent, list) else parent[token]
        del parent[tokens[-1]]
    return projected


def import_files(source_dir):
    data = ROOT / 'ryderesolve_evidence/data'
    archive = ROOT / 'sources/official/2026-10-15'
    archive.mkdir(parents=True, exist_ok=True)
    manifest = {'received_on': '2026-10-15', 'origin': 'organizer_attachments_supplied_by_user',
                'independently_authenticated': False, 'files': {}}
    catalog = json.loads((data / 'catalog.json').read_text(encoding='utf-8'))
    entries = {row['case_id']: row for row in catalog['cases']}
    for case, filename in FILES.items():
        contents = (source_dir / filename).read_bytes()
        archive_name = ('policy-v2.1' if case == 'policy' else case) + '.md'
        if (archive / archive_name).exists() and (archive / archive_name).read_bytes() != contents:
            raise ValueError(f'Archived source changed: {case}; create an explicit new source revision.')
        (archive / archive_name).write_bytes(contents)
        text = contents.decode('utf-8-sig')
        source = {'filename': filename, 'archive_path': f'sources/official/2026-10-15/{archive_name}',
                  'file_sha256': hashlib.sha256(contents).hexdigest()}
        if case == 'policy':
            lines = text.splitlines()
            starts = [(i, re.match(r'^### (?:Precedent )?(\d+\.\d+):?\s+(.*)', line))
                      for i, line in enumerate(lines)]
            sections = {}
            for i, match in starts:
                if not match:
                    continue
                end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith(('## ', '### '))), len(lines))
                body = lines[i + 1:end]
                while body and (not body[-1].strip() or body[-1] == '---'):
                    body.pop()
                sections[match[1]] = {'title': match[2], 'text': '\n'.join(body).strip(),
                                     'line_start': i + 1, 'line_end': i + 1 + len(body)}
            document = {'document_id': 'RYDE-POLICY-V2.1', 'title': 'Ryde Dispute Resolution Policy v2.1',
                        'version': '2.1', 'effective_date': '2026-01-01', 'source': source,
                        'sections': sections}
            write_json(data / 'policies/ryde-policy-v2.1.json', document)
            manifest['files'][case] = {**source, 'document_sha256': digest(document)}
            catalog['policy_documents'] = [{'document_id': document['document_id'],
                                            'path': 'policies/ryde-policy-v2.1.json',
                                            'sha256': digest(document)}]
            continue
        blocks = re.findall(r'```json\s*\n(.*?)```', text, re.S)
        if len(blocks) != 1:
            raise ValueError(f'Expected exactly one JSON block: {filename}')
        original = json.loads(blocks[0])
        raw = project_route(original) if case == 'DISP-001' else original
        manifest['files'][case] = {**source, 'original_json_sha256': digest(original),
                                  'runtime_json_sha256': digest(raw),
                                  'excluded_pointers': EXCLUDED if case == 'DISP-001' else [],
                                  'projection_reason': 'Exclude case answers and editorial adjudication; retained values and array indices unchanged.' if case == 'DISP-001' else 'JSON block unchanged; surrounding Markdown excluded.'}
        target = data / 'official' / (case + '.json')
        if case == 'DISP-002' and target.exists():
            if digest(json.loads(target.read_text(encoding='utf-8'))) != digest(raw):
                raise ValueError('DISP-002 changed: import as a new revision, do not overwrite.')
        else:
            write_json(target, raw)
        entries[case] = {**entries.get(case, {}), 'case_id': case,
                         'dispute_type': raw['dispute_ticket']['dispute_type'],
                         'data_origin': 'organizer_sample', 'policy_origin': 'organizer_sample',
                         'path': f'official/{case}.json', 'source_url': entries.get(case, {}).get('source_url'),
                         'source_sha256': digest(raw), 'policy_document_ids': ['RYDE-POLICY-V2.1'],
                         'description': 'Organizer records with separately versioned policy v2.1; see import manifest for source/projection details.'}
    catalog['cases'] = [entries[key] for key in sorted(entries)]
    write_json(data / 'catalog.json', catalog)
    write_json(archive / 'manifest.json', manifest)
    print(json.dumps({key: value.get('runtime_json_sha256', value.get('document_sha256'))
                      for key, value in manifest['files'].items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    import_files(parser.parse_args().source_dir)
