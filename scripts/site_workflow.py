#!/usr/bin/env python3
"""Versioned local website runs. No network, no publication, no installation."""
import argparse
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from urllib.parse import unquote, urlsplit

BEIJING = timezone(timedelta(hours=8))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def init_run(name, workspace, root=None):
    if not name.strip() or name in ('.','..') or re.search(r'[/\\\x00-\x1f]', name):
        raise ValueError('Site name must be a single nonempty folder name')
    parent = (Path(root).expanduser().resolve() if root else Path(workspace).resolve()/'output'/'websites')/name
    parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(BEIJING)
    stamp = now.strftime('%Y%m%d-%H%M%S')
    for version in range(1,10000):
        run = parent/('%s-v%02d'%(stamp,version))
        try: run.mkdir(); break
        except FileExistsError: continue
    else: raise ValueError('Too many versions for this timestamp')
    for directory in ('work','review'): (run/directory).mkdir()
    save(run/'run.json', {'schema_version':'1.0','name':name,'created_at':now.isoformat(),
         'timezone':'Asia/Shanghai','status':'prepared','paths':{'work':'work','site':'site','review':'review'},
         'note':'Only site/ and website.zip are deployment artifacts; work/ contains private source material.'})
    (run/'交付说明.md').write_text('# 网站交付\n\n当前状态：已创建工作目录，尚未生成网站。\n',encoding='utf-8')
    return run


class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.urls=[];self.ids=set();self.images=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        for key in ('src','href'):
            if key in attrs:self.urls.append(attrs[key])
        if tag=='img':self.images.append(attrs)


def inspect_site(site):
    errors=[];pages={};remote=[]
    for path in site.rglob('*.html'):
        parser=Links();parser.feed(path.read_text(encoding='utf-8'));pages[path.resolve()]=parser
    if (site/'index.html').resolve() not in pages:errors.append('Missing index.html')
    for path,parser in pages.items():
        for url in parser.urls:
            part=urlsplit(url)
            if part.scheme in ('http','https') or part.netloc:
                remote.append(url);continue
            if part.scheme in ('mailto','tel','data'):continue
            if part.scheme:errors.append('Unexpected URL scheme: '+part.scheme);continue
            target=(path.parent/unquote(part.path)).resolve() if part.path else path
            if not target.is_relative_to(site.resolve()):errors.append('Link leaves site folder: '+url);continue
            if not target.is_file():errors.append('Missing local resource: '+url);continue
            if part.fragment and target in pages and unquote(part.fragment) not in pages[target].ids:
                errors.append('Missing anchor: '+url)
        for img in parser.images:
            if 'alt' not in img:errors.append('Image without alt attribute in '+path.name)
    return {'status':'passed' if not errors else 'failed','errors':errors,'html_pages':len(pages),
            'remote_urls':sorted(set(remote)), 'scope':'Local HTML resources, anchors and alt attributes. Visual layout and interactions require browser review.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    start=sub.add_parser('init');start.add_argument('--name',required=True)
    start.add_argument('--workspace',default='.');start.add_argument('--root')
    build=sub.add_parser('build');build.add_argument('--run',required=True);build.add_argument('--data',required=True);build.add_argument('--styles')
    finish=sub.add_parser('deliver');finish.add_argument('--run',required=True)
    args=parser.parse_args()
    if args.command=='init':
        run=init_run(args.name,args.workspace,args.root)
        print(json.dumps({'run':str(run),'work':str(run/'work'),'site':str(run/'site'),'review':str(run/'review')},ensure_ascii=False));return
    run=Path(args.run).expanduser().resolve()
    manifest=json.loads((run/'run.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version')!='1.0':raise ValueError('Unknown run schema')
    site=run/'site'
    if args.command=='build':
        command=[sys.executable,'-S',str(Path(__file__).with_name('render_site.py')),str(Path(args.data).resolve()),str(site)]
        if args.styles:command+=['--styles',str(Path(args.styles).resolve())]
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode:raise ValueError(result.stderr.strip())
        manifest.update(status='built',data_file=str(Path(args.data).resolve()))
        save(run/'run.json',manifest)
        print(json.dumps({'index':str(site/'index.html'),'run':str(run)},ensure_ascii=False));return
    report=inspect_site(site);save(run/'review/structural-checks.json',report)
    if report['errors']:raise ValueError('; '.join(report['errors']))
    archive=run/'website.zip'
    if archive.exists():raise ValueError('Delivery archive exists; create a new run for a new version')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(site.rglob('*')):
            if path.is_file() and not path.is_symlink():z.write(path,path.relative_to(site))
    visual_file=run/'review/visual-checks.json'
    visual=json.loads(visual_file.read_text(encoding='utf-8')) if visual_file.exists() else {'status':'not_run'}
    manifest.update(status='delivered',visual_review=visual.get('status','unknown'))
    save(run/'run.json',manifest)
    notes=['# 网站交付','',f"站点：{manifest['name']}",'',
           '- [打开首页](site/index.html)','- [网站压缩包](website.zip)','- 内容、图片选择和来源记录：work/',
           '- [结构检查](review/structural-checks.json)',f"- 浏览器验证：{visual.get('status','not_run')}",'',
           '只部署 site/ 或解压后的 website.zip；work/ 和 review/ 不属于公开网站。',
           '下一次修改创建新的版本目录，保留原始资料与本版成果。']
    if visual.get('limitations'):notes+=['','验证范围限制：',*['- '+str(x) for x in visual['limitations']]]
    (run/'交付说明.md').write_text('\n'.join(notes)+'\n',encoding='utf-8')
    print(json.dumps({'run':str(run),'index':str(site/'index.html'),'archive':str(archive),'handoff':str(run/'交付说明.md'),'visual_review':visual.get('status')},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False),file=sys.stderr);sys.exit(2)
