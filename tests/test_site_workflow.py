import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from media_tools import inventory,select,dimensions,png
from site_workflow import init_run,inspect_site
from render_site import Site
from pypdf import PdfWriter
from pypdf.generic import NameObject,NumberObject,DictionaryObject,DecodedStreamObject


class WebsiteWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def render(self,data,name='site'):
        out=self.base/name;out.mkdir();Site(data,self.base,out,None).build();return out

    def test_versioned_output_and_custom_root(self):
        a=init_run('我的网站',self.base);b=init_run('我的网站',self.base)
        self.assertNotEqual(a,b);self.assertTrue((a/'work').is_dir());self.assertFalse((a/'site').exists())
        self.assertIn('+08:00',json.loads((a/'run.json').read_text())['created_at'])
        c=init_run('custom',self.base,self.base/'chosen');self.assertEqual(c.parent,(self.base/'chosen/custom').resolve())
        with self.assertRaises(ValueError):init_run('../escape',self.base)

    def test_pdf_image_extraction_and_no_identity_guess(self):
        result=inventory([ROOT/'tests/fixtures/scan.pdf'],self.base/'images')
        data=json.loads(Path(result['manifest']).read_text())
        self.assertEqual(result['images'],1);image=data['assets'][0]
        self.assertEqual(image['role'],'unassigned');self.assertEqual(image['use'],'pending')
        self.assertEqual(image['location']['page'],1)
        self.assertEqual(dimensions((self.base/'images'/image['file']).read_bytes()),(1200,900))

    def test_pdf_soft_mask_and_nested_form(self):
        writer=PdfWriter();page=writer.add_blank_page(width=100,height=100)
        mask=DecodedStreamObject();mask.set_data(b'\xff\x80\x00\xff')
        for key,val in {'/Type':'/XObject','/Subtype':'/Image','/ColorSpace':'/DeviceGray'}.items():mask[NameObject(key)]=NameObject(val)
        for key,val in {'/Width':2,'/Height':2,'/BitsPerComponent':8}.items():mask[NameObject(key)]=NumberObject(val)
        image=DecodedStreamObject();image.set_data(bytes([255,0,0]*4))
        for key,val in {'/Type':'/XObject','/Subtype':'/Image','/ColorSpace':'/DeviceRGB'}.items():image[NameObject(key)]=NameObject(val)
        for key,val in {'/Width':2,'/Height':2,'/BitsPerComponent':8}.items():image[NameObject(key)]=NumberObject(val)
        image[NameObject('/SMask')]=writer._add_object(mask)
        form=DecodedStreamObject();form.set_data(b'')
        form[NameObject('/Subtype')]=NameObject('/Form')
        form[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im'):writer._add_object(image)})})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):writer._add_object(DictionaryObject({NameObject('/Form'):writer._add_object(form)}))})
        path=self.base/'nested.pdf'
        with path.open('wb') as f:writer.write(f)
        result=inventory([path],self.base/'images');data=json.loads(Path(result['manifest']).read_text())
        self.assertEqual(result['warnings'],0);self.assertEqual(result['images'],1)
        asset=(self.base/'images'/data['assets'][0]['file']).read_bytes()
        self.assertEqual(asset[25],6)  # RGBA: retains the transparency mask.

    def test_docx_images_and_duplicate_sources(self):
        raw=png(2,2,3,bytes([12,34,56]*4));path=self.base/'photo.png';path.write_bytes(raw)
        doc=self.base/'test.docx'
        with zipfile.ZipFile(doc,'w') as z:z.writestr('word/media/image.png',raw)
        result=inventory([path,doc],self.base/'images');data=json.loads(Path(result['manifest']).read_text())
        self.assertEqual(result['images'],1);self.assertEqual(len(data['assets'][0]['occurrences']),1)
        selected=select(result['manifest'],data['assets'][0]['id'],'portrait','Synthetic test; not a real person','Test fixture',focal=(50,30))
        self.assertEqual(selected['position'],[50,30]);self.assertTrue(Path(selected['file']).exists())

    def test_unknown_media_and_empty_pdf_reported(self):
        bad=self.base/'bad.pdf';bad.write_text('broken')
        result=inventory([bad,ROOT/'tests/fixtures/text.pdf'],self.base/'images')
        self.assertEqual(result['images'],0);self.assertGreater(result['warnings'],0)

    def test_avatar_and_theme_in_all_pages(self):
        (self.base/'portrait.png').write_bytes(png(4,8,3,bytes([0,100,150]*32)))
        data={'name':'合成测试人物','portrait':{'file':'portrait.png','alt':'测试图片'},'design':{'theme':'editorial'},
              'projects':[{'id':'demo','title':'项目','sections':[{'title':'贡献','body':'保留原文'}]}]}
        out=self.render(data);self.assertFalse(inspect_site(out)['errors'])
        for p in out.glob('*.html'):
            value=p.read_text();self.assertIn('portrait-dialog',value);self.assertIn('aria-haspopup="dialog"',value);self.assertIn('site.js',value)
        self.assertTrue((out/'theme.css').is_file())

    def test_no_portrait_and_no_project_is_complete_page(self):
        out=self.render({'name':'短资料','intro':'只有一段说明'})
        self.assertFalse(inspect_site(out)['errors']);html=(out/'index.html').read_text()
        self.assertNotIn('portrait-trigger',html);self.assertNotIn('id="projects"',html)

    def test_caption_escaping_and_credit_link(self):
        (self.base/'photo.png').write_bytes(png(2,2,3,bytes([1,2,3]*4)))
        out=self.render({'name':'测试','hero_image':{'file':'photo.png','caption':'<script>bad</script>','credit':'Photographer','source_url':'https://example.com/photo'}})
        html=(out/'index.html').read_text();self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>bad',html)
        self.assertIn('https://example.com/photo',inspect_site(out)['remote_urls'])

    def test_delivery_excludes_private_work_and_refuses_overwrite(self):
        run=init_run('test',self.base);(run/'work/private.txt').write_text('private-data')
        data=run/'work/data.json';data.write_text(json.dumps({'name':'Test'}))
        cli=[sys.executable,'-S',str(ROOT/'scripts/site_workflow.py')]
        result=subprocess.run(cli+['build','--run',str(run),'--data',str(data)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        result=subprocess.run(cli+['deliver','--run',str(run)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with zipfile.ZipFile(run/'website.zip') as z:
            self.assertIn('index.html',z.namelist());self.assertFalse(any('private' in s or 'work/' in s for s in z.namelist()))
        self.assertEqual(json.loads((run/'run.json').read_text())['visual_review'],'not_run')
        result=subprocess.run(cli+['build','--run',str(run),'--data',str(data)],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)

    def test_structural_check_reports_bad_anchor_and_missing_image(self):
        site=self.base/'site';site.mkdir();(site/'index.html').write_text('<a href="#missing">x</a><img src="missing.png" alt="x">')
        result=inspect_site(site);self.assertEqual(result['status'],'failed');self.assertEqual(len(result['errors']),2)


if __name__=='__main__':unittest.main()
