#!/usr/bin/env python3
"""Read -> organize -> review. Python 3.9+, no network or runtime installation."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from document_io import extract_one, ocr_binary
from content_organizer import organize, outline_markdown, validate_review


def dump(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def doctor():
    try:
        import pypdf
        pdf={'available':True,'version':pypdf.__version__,'module':str(Path(pypdf.__file__).resolve())}
    except Exception as e:
        pdf={'available':False,'error':str(e)}
    ocr={'available':False,'reason':'No matching local OCR helper; scanned pages will be reported as unresolved.'}
    binary=ocr_binary()
    if binary:
        try:
            process=subprocess.run([str(binary),'--check'],capture_output=True,text=True,timeout=20)
            if process.returncode==0:ocr={'available':True,'binary':str(binary),**json.loads(process.stdout)}
            else:ocr={'available':False,'error':process.stderr.strip()[:300]}
        except Exception as e:ocr={'available':False,'error':str(e)}
    result={'python':sys.version.split()[0],'executable':sys.executable,'platform':platform.platform(),
            'core_ready':sys.version_info>=(3,9) and pdf['available'],
            'formats':{'markdown':True,'txt':True,'docx':True,'pdf_text':pdf['available'],'legacy_doc':False},
            'pdf_parser':pdf,'offline_ocr':ocr,
            'network_required':False,'automatic_install':False}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['core_ready'] else 2


def read_json(path):
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value,dict):raise ValueError('JSON root must be an object')
    return value


def check_bundle(bundle):
    if bundle.get('schema_version')!='1.0' or not isinstance(bundle.get('documents'),list):
        raise ValueError('Expected a version 1.0 extraction bundle')
    if not bundle['documents']:raise ValueError('Bundle has no documents')
    for doc in bundle['documents']:
        if not isinstance(doc,dict) or not isinstance(doc.get('blocks'),list) or not isinstance(doc.get('source'),dict):
            raise ValueError('Invalid document entry in bundle')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('doctor',help='Check local capabilities; no install or network')
    extract=commands.add_parser('extract',help='Read documents into bundle.json, extracted.md and assets/')
    extract.add_argument('inputs',nargs='+')
    extract.add_argument('--out',required=True,help='A NEW output directory; existing paths are refused')
    extract.add_argument('--encoding',help='Explicit text encoding when UTF-8/UTF-16 detection is insufficient')
    extract.add_argument('--ocr',choices=['auto','always','never'],default='auto')
    extract.add_argument('--max-pages',type=int,default=500)
    extract.add_argument('--password-env',help='Environment variable containing a PDF password; not serialized')
    prepare=commands.add_parser('organize',help='Create traceable outline, content-plan.json and review-template.json')
    prepare.add_argument('bundle')
    prepare.add_argument('--out',required=True)
    validate=commands.add_parser('validate-review',help='Check source references and coverage; does NOT certify semantics')
    validate.add_argument('bundle')
    validate.add_argument('review')
    args=parser.parse_args()
    if args.command=='doctor':return doctor()
    if args.command=='validate-review':
        bundle=read_json(args.bundle);check_bundle(bundle)
        result=validate_review(bundle,read_json(args.review))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if not result['valid'] else (3 if result['flags'] else 0)
    out=Path(args.out).expanduser().resolve()
    if out.exists():raise ValueError('Output already exists; choose a new directory: '+str(out))
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.'+out.name+'-',dir=out.parent))
    try:
        if args.command=='extract':
            if args.max_pages<1:raise ValueError('--max-pages must be positive')
            password=os.environ.get(args.password_env) if args.password_env else None
            if args.password_env and password is None:raise ValueError('Requested password environment variable is not set')
            (temp/'assets').mkdir()
            docs=[]
            paths=set()
            for source in args.inputs:
                resolved=str(Path(source).expanduser().resolve())
                if resolved in paths:continue
                paths.add(resolved)
                docs.append(extract_one(resolved,temp/'assets',args.encoding,args.ocr,args.max_pages,password))
            bundle={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(),
                    'documents':docs,'coverage_meaning':'extracted = readable text processed, not fact-checked or layout-verified; see warnings',
                    'summary':{'documents':len(docs),'blocks':sum(len(d['blocks']) for d in docs),'partial':sum(d['status']=='partial' for d in docs),'errors':sum(d['status']=='error' for d in docs)}}
            dump(temp/'bundle.json',bundle)
            plan=organize(bundle)
            (temp/'extracted.md').write_text(outline_markdown(plan),encoding='utf-8')
            result={'output':str(out),'bundle':str(out/'bundle.json'),**bundle['summary'],
                    'documents_status':[{'file':d['source']['name'],'status':d['status'],'warning_codes':sorted(set(w['code'] for w in d['warnings']))} for d in docs]}
            code=2 if bundle['summary']['errors'] else (3 if bundle['summary']['partial'] else 0)
        else:
            bundle=read_json(args.bundle);check_bundle(bundle)
            plan=organize(bundle)
            plan['input_bundle']=str(Path(args.bundle).resolve())
            dump(temp/'content-plan.json',plan)
            dump(temp/'review-template.json',{'claims':[],'coverage':plan['coverage'],'conflicts':[]})
            (temp/'outline.md').write_text(outline_markdown(plan),encoding='utf-8')
            result={'output':str(out),'sections':len(plan['sections']),'source_blocks':len(plan['source_blocks']),'quantity_candidates':len(plan['quantity_candidates']),'publication_ready':False}
            code=0
        # Never replace an existing output, including one created concurrently.
        if out.exists():raise ValueError('Output appeared during processing; refused to overwrite')
        temp.rename(out)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return code
    finally:
        if temp.exists():shutil.rmtree(temp)


if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False),file=sys.stderr)
        sys.exit(2)
