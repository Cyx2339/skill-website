#!/usr/bin/env python3
"""Inspect package installation; optionally restore owner execute on verified bundled OCR only."""
import argparse
import hashlib
import json
from pathlib import Path
import stat


def check(root, repair=False):
    expected=json.loads((root/'scripts/bin/checksums.json').read_text())
    results=[]
    for name,digest in expected.items():
        if Path(name).name!=name:raise ValueError('Invalid manifest entry')
        path=root/'scripts/bin'/name
        if path.is_symlink():raise ValueError('Refusing symlinked helper')
        if not path.is_file():
            results.append({'file':name,'status':'missing'});continue
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            results.append({'file':name,'status':'hash_mismatch'});continue
        executable=bool(path.stat().st_mode & stat.S_IXUSR)
        if repair and not executable:
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        results.append({'file':name,'status':'repaired' if repair and not executable else ('ready' if executable else 'not_executable')})
    return {'files':results,'ready':bool(results) and all(r['status'] in ('ready','repaired') for r in results),
            'scope':'Package file integrity/mode only; platform runtime support is checked by doctor.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repair-ocr-mode',action='store_true')
    args=parser.parse_args()
    try:
        result=check(Path(__file__).resolve().parents[1],args.repair_ocr_mode)
        print(json.dumps(result,indent=2));raise SystemExit(0 if result['ready'] else 3)
    except (ValueError,OSError) as error:
        print(json.dumps({'error':str(error)}));raise SystemExit(2)
