#!/usr/bin/env python3
"""Local image inventory and explicit role selection. No face identity inference."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile
import zipfile
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor'))
from pypdf import PdfReader

TYPES={'.png','.jpg','.jpeg','.webp','.gif','.avif'}


def dimensions(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data)>=24:return struct.unpack('>II',data[16:24])
    if data[:6] in (b'GIF87a',b'GIF89a') and len(data)>=10:return struct.unpack('<HH',data[6:10])
    if data[:2]==b'\xff\xd8':
        i=2
        while i+4<=len(data):
            if data[i]!=255:break
            while i<len(data) and data[i]==255:i+=1
            if i>=len(data):break
            marker=data[i];i+=1
            if marker in (0xd8,0xd9,0x01) or 0xd0<=marker<=0xd7:continue
            if i+2>len(data):break
            size=int.from_bytes(data[i:i+2],'big')
            if size<2 or i+size>len(data):break
            if marker in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf) and size>=7:
                return int.from_bytes(data[i+5:i+7],'big'),int.from_bytes(data[i+3:i+5],'big')
            i+=size
    return None,None


def png(width,height,channels,data):
    if len(data)!=width*height*channels:raise ValueError('Unexpected image sample length')
    def chunk(kind,value):return struct.pack('>I',len(value))+kind+value+struct.pack('>I',zlib.crc32(kind+value)&0xffffffff)
    color={1:0,2:4,3:2,4:6}[channels]
    rows=b''.join(b'\0'+data[y*width*channels:(y+1)*width*channels] for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,color,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')


def pdf_image(obj):
    w,h=int(obj['/Width']),int(obj['/Height'])
    if w<=0 or h<=0 or w*h>16_000_000:raise ValueError('Invalid image dimensions or image exceeds 16 megapixels')
    filters=obj.get('/Filter',[])
    if isinstance(filters,str):filters=[filters]
    if '/DCTDecode' in filters and not obj.get('/SMask') and not obj.get('/Mask'):
        if obj.get('/Decode'):raise ValueError('JPEG decode mapping needs visual conversion')
        return '.jpg',obj.get_data(),w,h
    if int(obj.get('/BitsPerComponent',0))!=8 or obj.get('/Decode') or obj.get('/Mask'):
        raise ValueError('Only unmodified 8-bit grayscale/RGB samples or plain JPEG are supported')
    space=obj.get('/ColorSpace');channels={'/DeviceRGB':3,'/DeviceGray':1}.get(str(space))
    if not channels:raise ValueError('Unsupported PDF image color space: '+str(space))
    raw=obj.get_data()
    if len(raw)!=w*h*channels:raise ValueError('Unexpected image sample length')
    if obj.get('/SMask'):
        mask=obj['/SMask'].get_object()
        if int(mask.get('/Width',0))!=w or int(mask.get('/Height',0))!=h or int(mask.get('/BitsPerComponent',0))!=8 or mask.get('/Decode'):
            raise ValueError('Unsupported transparency mask')
        alpha=mask.get_data()
        if len(alpha)!=w*h:raise ValueError('Unsupported transparency mask data')
        raw=b''.join(raw[n*channels:(n+1)*channels]+alpha[n:n+1] for n in range(w*h));channels+=1
    return '.png',png(w,h,channels,raw),w,h


def inventory(inputs,out):
    out=Path(out).expanduser().resolve()
    if out.exists():raise ValueError('Choose a new inventory directory')
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.media-',dir=out.parent));(temp/'assets').mkdir()
    result={'schema_version':'1.0','assets':[],'warnings':[],
            'portrait_status':'unreviewed','notes':'Image extraction does not identify the owner. Inspect candidates before selecting a portrait. No images are published automatically.'}
    seen={}
    def add(data,suffix,source,location,width=None,height=None):
        digest=hashlib.sha256(data).hexdigest()
        if digest in seen:
            seen[digest]['occurrences'].append({'source':str(source),'location':location});return
        if width is None:width,height=dimensions(data)
        item={'id':'image-'+digest[:12],'file':'assets/'+digest[:16]+suffix,'sha256':digest,
              'width':width,'height':height,'bytes':len(data),'role':'unassigned','use':'pending',
              'source':str(source),'location':location,'occurrences':[],'source_url':'','credit':'','usage_basis':'',
              'focal_point':[50,50], 'review_note':''}
        (temp/item['file']).write_bytes(data);result['assets'].append(item);seen[digest]=item
    try:
        for value in inputs:
            path=Path(value).expanduser().resolve()
            try:
                if path.stat().st_size>100*1024*1024:raise ValueError('Input exceeds 100 MiB')
                if path.suffix.lower() in TYPES:add(path.read_bytes(),path.suffix.lower(),path,{'kind':'local_file'})
                elif path.suffix.lower()=='.docx':
                    with zipfile.ZipFile(path) as z:
                        if len(z.infolist())>6000 or sum(i.file_size for i in z.infolist())>160*1024*1024:raise ValueError('DOCX archive exceeds extraction limit')
                        for member in sorted(z.namelist()):
                            if member.startswith('word/media/') and not member.endswith('/'):
                                suffix=Path(member).suffix.lower()
                                if suffix in TYPES:add(z.read(member),suffix,path,{'member':member})
                                else:result['warnings'].append({'source':str(path),'member':member,'message':'Image type needs conversion: '+suffix})
                elif path.suffix.lower()=='.pdf':
                    reader=PdfReader(str(path))
                    if reader.is_encrypted and not reader.decrypt(''):raise ValueError('Protected PDF image extraction is unavailable; use an unlocked copy')
                    for number,page in enumerate(reader.pages,1):
                        visited=set()
                        def walk(resources,trail=''):
                            if not resources:return
                            objects=resources.get_object().get('/XObject',{})
                            if hasattr(objects,'get_object'):objects=objects.get_object()
                            for key,value in objects.items():
                                obj=value.get_object();identity=id(obj)
                                if identity in visited:continue
                                visited.add(identity)
                                if obj.get('/Subtype')=='/Form':walk(obj.get('/Resources'),trail+key)
                                elif obj.get('/Subtype')=='/Image':
                                    try:
                                        suffix,data,w,h=pdf_image(obj);add(data,suffix,path,{'page':number,'object':trail+key},w,h)
                                    except Exception as error:result['warnings'].append({'source':str(path),'page':number,'object':trail+key,'message':str(error)})
                        walk(page.get('/Resources'))
                        if re.search(rb'(?:^|\s)BI(?:\s|$)',page.get_contents().get_data() if page.get_contents() else b''):
                            result['warnings'].append({'source':str(path),'page':number,'message':'Inline images may require page rendering and visual extraction'})
                else:raise ValueError('Unsupported media source: '+path.suffix)
            except Exception as error:result['warnings'].append({'source':str(path),'message':str(error)})
        if not result['assets']:result['portrait_status']='no_extracted_images'
        (temp/'media-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if out.exists():raise ValueError('Output appeared during extraction; refusing replacement')
        temp.rename(out)
        return {'manifest':str(out/'media-manifest.json'),'images':len(result['assets']),'warnings':len(result['warnings'])}
    finally:
        if temp.exists():shutil.rmtree(temp)


def select(manifest,asset_id,role,reason,usage_basis,source_url='',credit='',focal=(50,50)):
    path=Path(manifest).resolve();data=json.loads(path.read_text(encoding='utf-8'))
    items=[a for a in data['assets'] if a['id']==asset_id]
    if len(items)!=1:raise ValueError('Select one known asset ID')
    if not reason.strip() or not usage_basis.strip():raise ValueError('Record visual review and basis for use')
    if len(focal)!=2 or any(not 0<=v<=100 for v in focal):raise ValueError('Focal point values must be between 0 and 100')
    item=items[0];media=(path.parent/item['file']).resolve()
    if not media.is_relative_to(path.parent) or not media.is_file():raise ValueError('Invalid local asset')
    if role=='portrait':
        for a in data['assets']:
            if a is not item and a.get('role')=='portrait' and a.get('use')=='selected':
                raise ValueError('A portrait is already selected; review that decision first')
        data['portrait_status']='selected_after_visual_review'
    item.update(role=role,use='selected',review_note=reason,usage_basis=usage_basis,source_url=source_url,credit=credit,focal_point=list(focal))
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'file':str(media),'alt':'', 'position':list(focal),'source_url':source_url,'credit':credit}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    inv=sub.add_parser('inventory');inv.add_argument('inputs',nargs='+');inv.add_argument('--out',required=True)
    pick=sub.add_parser('select');pick.add_argument('manifest');pick.add_argument('--id',required=True)
    pick.add_argument('--role',choices=['portrait','project','atmosphere','interest'],required=True)
    pick.add_argument('--reason',required=True);pick.add_argument('--usage-basis',required=True)
    pick.add_argument('--source-url',default='');pick.add_argument('--credit',default='');pick.add_argument('--focal',nargs=2,type=float,default=[50,50])
    args=p.parse_args()
    result=inventory(args.inputs,args.out) if args.command=='inventory' else select(args.manifest,args.id,args.role,args.reason,args.usage_basis,args.source_url,args.credit,args.focal)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False),file=sys.stderr);sys.exit(2)
