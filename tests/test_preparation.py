import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_site import prepare
from skill_setup import check
from document_tools import capabilities
from render_site import Site
from site_workflow import inspect_site


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.doc=self.base/'resume.md'
        self.doc.write_text('# Synthetic person\n\nA researcher.\n\n## Honors\n\nSynthetic award.\n')
    def tearDown(self):self.temp.cleanup()
    def prepare(self,inputs=None):
        return prepare(inputs or [self.doc],'Test',self.base,ocr='never')
    def cli(self,*args):
        return subprocess.run([sys.executable,'-S',str(ROOT/'scripts/site_workflow.py'),*map(str,args)],capture_output=True,text=True)
    def test_prepare_preserves_source_and_build_delivery(self):
        before=self.doc.read_bytes();report,code=self.prepare()
        self.assertEqual(code,0,report);run=Path(report['run'])
        self.assertEqual(self.doc.read_bytes(),before)
        self.assertTrue(all(Path(p).exists() for p in report['next_read']))
        bundle=json.loads((run/'work/read/bundle.json').read_text())
        blocks=[b for d in bundle['documents'] for b in d['blocks']]
        review={'claims':[{'id':'c'+str(i),'text':b['text'],'source_refs':[b['id']],'verification':'supported'} for i,b in enumerate(blocks)],
                'coverage':[{'block_id':b['id'],'decision':'include','reason':'Test coverage'} for b in blocks],'conflicts':[]}
        (run/'work/reviewed-content.json').write_text(json.dumps(review))
        data=run/'work/site-data.json';data.write_text(json.dumps({'name':'Synthetic person','honors':[{'title':'Synthetic award'}]}))
        result=self.cli('build','--run',run,'--data',data)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((run/'review/content-checks.json').exists())
        checks=run/'review/browser';checks.mkdir();(checks/'browser-checks.json').write_text('{"status":"passed"}')
        result=self.cli('deliver','--run',run);self.assertEqual(result.returncode,0,result.stderr)
        manifest=json.loads((run/'run.json').read_text())
        self.assertEqual(manifest['visual_review'],'not_run')
        self.assertEqual(manifest['browser_reports'][0]['status'],'passed')
        self.assertTrue((run/'website.zip').exists())
    def test_failed_input_does_not_lose_other_document(self):
        bad=self.base/'broken.pdf';bad.write_text('not a PDF')
        report,code=self.prepare([self.doc,bad])
        self.assertEqual(code,2);self.assertEqual(report['status'],'error')
        run=Path(report['run']);self.assertIn('Synthetic person',(run/'work/read/extracted.md').read_text())
        self.assertTrue((run/'work/content/review-template.json').exists())
        self.assertTrue(any(d['status']=='error' for d in report['document_warnings']))
    def test_missing_input_creates_no_run(self):
        with self.assertRaises(ValueError):self.prepare([self.base/'missing.pdf'])
        self.assertFalse((self.base/'output').exists())
    def test_timeout_records_stage_and_returns(self):
        with patch('prepare_site.capabilities',return_value={'core_ready':True}),patch('prepare_site.shutil.which',return_value=None),patch('prepare_site.subprocess.run',side_effect=subprocess.TimeoutExpired('extract',1)):
            report,code=self.prepare()
        self.assertEqual(code,2);self.assertEqual(report['stages'][0]['stage'],'extract')
        log=json.loads((Path(report['run'])/'work/extract-log.json').read_text())
        self.assertEqual(log['error'],'stage_timeout')
    def test_abnormal_child_exit_is_an_error(self):
        with patch('prepare_site.capabilities',return_value={'core_ready':True}),patch('prepare_site.shutil.which',return_value=None),patch('prepare_site.subprocess.run',return_value=subprocess.CompletedProcess([], -9, '', 'terminated')):
            report,code=self.prepare()
        self.assertEqual(code,2);self.assertEqual(report['status'],'error')
    def test_build_requires_review_and_rejects_invalid_reference(self):
        report,_=self.prepare();run=Path(report['run']);data=run/'work/data.json';data.write_text('{"name":"Test"}')
        self.assertEqual(self.cli('build','--run',run,'--data',data).returncode,2)
        (run/'work/reviewed-content.json').write_text(json.dumps({'claims':[{'id':'bad','text':'Invented','source_refs':['missing']}],'coverage':[],'conflicts':[]}))
        self.assertEqual(self.cli('build','--run',run,'--data',data).returncode,2)
        self.assertFalse((run/'site').exists())
    def test_all_honors_render_and_have_navigation(self):
        out=self.base/'site';out.mkdir()
        Site({'name':'Test','honors':[{'title':'Award '+str(i)} for i in range(6)]},self.base,out,None).build()
        html=(out/'index.html').read_text()
        for i in range(6):self.assertIn('Award '+str(i),html)
        self.assertIn('href="#honors"',html);self.assertFalse(inspect_site(out)['errors'])


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.bin=self.root/'scripts/bin';self.bin.mkdir(parents=True)
        self.helper=self.bin/'helper';self.helper.write_bytes(b'synthetic, never executed');self.helper.chmod(0o644)
        (self.bin/'checksums.json').write_text(json.dumps({'helper':hashlib.sha256(self.helper.read_bytes()).hexdigest()}))
    def tearDown(self):self.temp.cleanup()
    def test_mode_repair_is_scoped_and_preserves_content(self):
        before=self.helper.read_bytes();self.assertEqual(check(self.root)['files'][0]['status'],'not_executable')
        result=check(self.root,True);self.assertTrue(result['ready']);self.assertEqual(self.helper.read_bytes(),before)
        self.assertEqual(stat.S_IMODE(self.helper.stat().st_mode),0o744)
        self.assertEqual(check(self.root,True)['files'][0]['status'],'ready')
    def test_tampered_binary_not_repaired(self):
        self.helper.write_bytes(b'changed');self.assertFalse(check(self.root,True)['ready'])
        self.assertEqual(stat.S_IMODE(self.helper.stat().st_mode),0o644)
    def test_symlink_refused(self):
        other=self.root/'outside';self.helper.rename(other);self.helper.symlink_to(other)
        with self.assertRaises(ValueError):check(self.root,True)
        self.assertEqual(stat.S_IMODE(other.stat().st_mode),0o644)
    def test_doctor_distinguishes_execution_permission(self):
        with patch('document_tools.ocr_candidate',return_value=self.helper),patch('document_tools.ocr_binary',return_value=None):
            result=capabilities()
        self.assertEqual(result['offline_ocr']['code'],'not_executable');self.assertTrue(result['core_ready'])

if __name__=='__main__':unittest.main()
