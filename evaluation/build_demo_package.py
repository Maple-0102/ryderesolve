"""Build static, offline recording pages from retained run reports; no providers."""
from hashlib import sha256
from html import escape
from pathlib import Path
import argparse
import json
import os
import re
from ryde_resolve.ui import render_html

LABELS = {
    'R21-FARE-ORIGINAL': '官方 Fare：未通知加价',
    'R21-ROUTE-ORIGINAL': '官方 Route：超出 AI 权限',
    'R21-NOSHOW-ORIGINAL': '官方 No-show：政策待澄清',
    'R21-FARE-NOTIFIED': '合成对照：通知记录完整',
    'R21-FARE-NOTICE-MISSING': '合成对照：通知记录缺失',
}
ORDER = {key: i for i, key in enumerate(LABELS)}


def build(sources, output):
    output = Path(output)
    if (output / 'index.html').exists():
        raise ValueError('Choose a new output directory; retain previous recordings.')
    output.mkdir(parents=True, exist_ok=True)
    cards, entries, seen = [], [], set()
    source_reports = []
    for source in sources:
        source = Path(source)
        if not source.resolve().is_relative_to(output.parent.resolve()):
            raise ValueError('Keep source reports under the recording directory parent.')
        report = json.loads(source.read_text())
        source_reports.append({'path':os.path.relpath(source.resolve(),output.resolve()),
                               'sha256':sha256(source.read_bytes()).hexdigest()})
        replay = report['kind'].startswith('offline revalidation')
        if not replay and not report['kind'].startswith('fresh '):
            raise ValueError('Recording package requires an explicitly fresh or offline-revalidation report.')
        for row in report['results']:
            key = row['exercise_id']
            if key in seen:
                raise ValueError('Duplicate exercise: ' + key)
            if not re.fullmatch(r'[A-Za-z0-9-]+', key):
                raise ValueError('Unsafe exercise identifier')
            seen.add(key)
            run = row['run']
            stem = key.lower()
            title = LABELS.get(key, key)
            origin = run['snapshot']['audit']['data_origin']
            mode = ('离线复验：双方 Advocate 与 Judge 均沿用已保存输出，展示当前程序检查结果。'
                    if replay else '真实模型调用的保存记录：展示这次运行结果；打开本页不会再次调用模型。')
            banner = (f'<aside class="recording-banner" style="padding:16px;background:#fff3cd;color:#332701">'
                      f'<b>{escape(title)}</b><p>{escape(mode)}</p>'
                      '<p>这是事后记录，页面不执行退款。请同时展示原始检查与程序修正。</p>'
                      '<a href="index.html">返回演示目录</a></aside>')
            path = render_html([run], output / (stem + '.html'))
            path.write_text(path.read_text().replace('<body>', '<body>' + banner, 1))
            (output / (stem + '.run.json')).write_text(json.dumps(run, ensure_ascii=False, indent=2) + '\n')
            entry = {'exercise_id': key, 'title': title, 'origin': origin, 'replayed': replay,
                     'source_sha256': sha256(source.read_bytes()).hexdigest(),
                     'runtime_implementation': report['runtime_implementation'],
                     'validation_errors': run['validation_errors'], 'first_pass_valid': run.get('first_pass_valid'),
                     'adjustments': len(run.get('judge_adjustments', [])),
                     'decision': run['ruling']['decision'], 'refund_amount': run['ruling']['refund_amount'],
                     'html': path.name, 'run_json': stem + '.run.json'}
            entries.append(entry)
            state = '检查通过' if not run['validation_errors'] else '检查未通过，保留失败'
            cards.append((ORDER.get(key, 99), f'<li><a href="{escape(path.name)}">{escape(title)}</a>'
                          f'<p>{escape(mode)} {state}；首次输出通过：{escape(str(run.get("first_pass_valid")))}；'
                          f'程序修正：{entry["adjustments"]} 项。来源：{escape(origin)}。</p></li>'))
    html = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>RydeResolve 录屏入口</title><style>body{font:18px/1.65 system-ui;max-width:1050px;margin:40px auto;padding:0 24px;background:#f4f7fb;color:#182a41}li{background:white;border-radius:12px;padding:20px;margin:20px 0}a{color:#075da8}h1{font-size:32px}</style>'
            '<h1>RydeResolve · 录屏入口</h1><p>建议顺序：Fare 完整流程 → Route 权限边界 → No-show 政策缺口。额外的团队合成对照会分别标明。</p>'
            '<p>全部页面可以离线打开，不需要账号，不会调用模型或执行退款。真实调用保存记录与离线复验分别标明；这些已知开发案例不代表模型准确率。</p><ol>'
            + ''.join(card for _, card in sorted(cards, key=lambda x: x[0])) + '</ol></html>')
    (output / 'index.html').write_text(html)
    manifest = {'kind': 'static recording package', 'opening_provider_calls': 0,
                'source_reports':source_reports, 'entries': entries,
                'files':{p.name:sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())
                         if p.suffix in ('.html','.json')}}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
    print(args.output / 'index.html')


if __name__ == '__main__':
    main()
