#!/usr/bin/env python3
"""One bounded local call: create run, check capabilities, extract, organize, inventory. No install/network."""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from document_tools import capabilities
from site_workflow import init_run,save

SCRIPTS=Path(__file__).resolve().parent


def prepare(inputs,name,workspace,root=None,image_viewing='unknown',browser_control='unknown',timeout=180,ocr='auto'):
    paths=list(dict.fromkeys(str(Path(p).expanduser().resolve()) for p in inputs))
    if not paths or any(not Path(p).is_file() for p in paths):raise ValueError('All inputs must be existing files')
    run=init_run(name,workspace,root);work=run/'work'
    env=capabilities()
    env.update(image_viewing={'status':image_viewing,'basis':'Reported by host/agent, not detected by Python'},
               browser_control={'status':browser_control,'basis':'Reported by host/agent; unknown is not unavailable'},
               node_path=shutil.which('node'))
    if env['node_path']:
        try:
            probe=subprocess.run([env['node_path'],str(SCRIPTS/'browser_check.mjs'),'--probe'],capture_output=True,text=True,timeout=10)
            env['browser_fallback']=json.loads(probe.stdout) if probe.stdout.strip() else {'ready':False,'reason':probe.stderr[:300]}
        except (OSError,ValueError,subprocess.TimeoutExpired) as error:
            env['browser_fallback']={'ready':False,'reason':str(error)}
    else:env['browser_fallback']={'ready':False,'reason':'Node not installed; do not install during generation'}
    save(work/'capabilities.json',env)
    stages=[]
    def stage(key,script,args):
        start=time.monotonic()
        try:
            result=subprocess.run([sys.executable,'-S',str(SCRIPTS/script),*args],capture_output=True,text=True,timeout=timeout)
            payload={'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
            code=result.returncode if result.returncode in (0,2,3) else 2
        except subprocess.TimeoutExpired:
            payload={'returncode':2,'error':'stage_timeout','seconds':timeout};code=2
        except OSError as error:
            payload={'returncode':2,'error':str(error)};code=2
        save(work/(key+'-log.json'),payload)
        stages.append({'stage':key,'exit_code':code,'seconds':round(time.monotonic()-start,3),'log':key+'-log.json'})
        return code
    code=2
    if env['core_ready']:
        code=stage('extract','document_tools.py',['extract',*paths,'--out',str(work/'read'),'--ocr',ocr])
        if (work/'read/bundle.json').is_file():
            organize_code=stage('organize','document_tools.py',['organize',str(work/'read/bundle.json'),'--out',str(work/'content')])
            if organize_code==2:code=2
            elif organize_code==3 and code==0:code=3
        media=[p for p in paths if Path(p).suffix.lower() in ('.pdf','.docx','.png','.jpg','.jpeg','.webp','.gif','.avif')]
        if media:
            media_code=stage('media','media_tools.py',['inventory',*media,'--out',str(work/'media')])
            if media_code==2:code=2
            elif media_code==3 and code==0:code=3
    warnings=[]
    if (work/'read/bundle.json').exists():
        bundle=json.loads((work/'read/bundle.json').read_text())
        warnings=[{'source':d['source']['name'],'status':d['status'],'warnings':d['warnings']} for d in bundle['documents']]
    media_warnings=[]
    if (work/'media/media-manifest.json').exists():
        media_warnings=json.loads((work/'media/media-manifest.json').read_text()).get('warnings',[])
        if media_warnings and code==0:code=3
    report={'run':str(run),'status':{0:'prepared',3:'partial'}.get(code,'error'),'stages':stages,
            'document_warnings':warnings,'media_warnings':media_warnings,'semantic_review':'required',
            'next_read':[str(p) for p in (work/'read/extracted.md',work/'content/review-template.json',work/'media/media-manifest.json') if p.exists()],
            'capabilities':str(work/'capabilities.json')}
    save(work/'prepare-report.json',report)
    manifest=json.loads((run/'run.json').read_text());manifest['status']=report['status'];save(run/'run.json',manifest)
    return report,code


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('inputs',nargs='+');p.add_argument('--name',required=True)
    p.add_argument('--workspace',default='.');p.add_argument('--root');p.add_argument('--timeout',type=int,default=180)
    p.add_argument('--ocr',choices=['auto','always','never'],default='auto')
    p.add_argument('--image-viewing',choices=['unknown','available','unavailable'],default='unknown')
    p.add_argument('--browser-control',choices=['unknown','host','unavailable'],default='unknown')
    a=p.parse_args()
    try:
        if not 1<=a.timeout<=1800:raise ValueError('timeout must be 1..1800 seconds')
        report,code=prepare(a.inputs,a.name,a.workspace,a.root,a.image_viewing,a.browser_control,a.timeout,a.ocr)
        print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(code)
    except (ValueError,OSError) as error:
        print(json.dumps({'error':str(error)}),file=sys.stderr);raise SystemExit(2)
