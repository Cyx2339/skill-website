"""Local, provenance-preserving extraction. Source documents are never modified."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

VENDOR = Path(__file__).resolve().parent / 'vendor'
sys.path.insert(0, str(VENDOR))
MAX_INPUT = 100 * 1024 * 1024
MAX_ZIP = 160 * 1024 * 1024
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
NS = {'w': W[1:-1]}


class InputProblem(Exception):
    pass


def warning(doc, code, message, severity='review', **location):
    item = {'code': code, 'severity': severity, 'message': message}
    if location:
        item['location'] = location
    doc['warnings'].append(item)


def block(doc, kind, text, location, **extra):
    item = {'id': '%s:b%05d' % (doc['id'], len(doc['blocks']) + 1),
            'type': kind, 'text': text, 'location': location, **extra}
    doc['blocks'].append(item)
    return item


def xml(data):
    # OOXML has no need for document type declarations or entities.
    if re.search(br'<!\s*(DOCTYPE|ENTITY)', data, re.I):
        raise InputProblem('XML contains a DTD/entity declaration; refused')
    return ET.fromstring(data)


def decode_text(data, encoding=None):
    if encoding:
        return data.decode(encoding, errors='strict'), encoding
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16'), 'utf-16'
    try:
        return data.decode('utf-8-sig'), 'utf-8'
    except UnicodeDecodeError:
        raise InputProblem('Unknown text encoding. Specify --encoding (for example gb18030); no lossy replacement was used.')


def text_links(text):
    result = []
    for match in re.finditer(r'(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)', text):
        result.append({'label': match[1], 'target': match[2]})
    return result


def extract_text_file(path, doc, assets, encoding=None):
    text, detected = decode_text(path.read_bytes(), encoding)
    doc['source']['encoding'] = detected
    doc['raw_text'] = text
    markdown = path.suffix.lower() in ('.md', '.markdown')
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        start = i
        line = lines[i]
        fence = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line) if markdown else None
        if fence:
            i += 1
            while i < len(lines) and not re.match(r'^\s{0,3}' + re.escape(fence[1][0]) + '{' + str(len(fence[1])) + r',}\s*$', lines[i]):
                i += 1
            closed = i < len(lines)
            i += int(closed)
            block(doc, 'code', '\n'.join(lines[start:i]), {'line_start': start + 1, 'line_end': i}, language=fence[2].strip())
            if not closed:
                warning(doc, 'UNCLOSED_CODE_FENCE', 'Code fence is not closed; text was preserved.', line=start + 1)
            continue
        heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line) if markdown else None
        setext = markdown and i + 1 < len(lines) and re.fullmatch(r'\s*(=+|-+)\s*', lines[i + 1])
        if heading or setext:
            end = i + (2 if setext and not heading else 1)
            block(doc, 'heading', heading[2] if heading else line.strip(), {'line_start': i + 1, 'line_end': end}, level=len(heading[1]) if heading else (1 if '=' in lines[i+1] else 2))
            i = end
            continue
        if markdown and i + 1 < len(lines) and '|' in line and re.match(r'^\s*\|?\s*:?-{3,}', lines[i+1]):
            i += 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                i += 1
            raw = '\n'.join(lines[start:i])
            rows = [[cell.strip() for cell in row.strip().strip('|').split('|')] for row in [lines[start]] + lines[start+2:i]]
            block(doc, 'table', raw, {'line_start': start+1, 'line_end': i}, rows=rows)
            if '\\|' in raw or '`' in raw:
                warning(doc, 'MARKDOWN_TABLE_COMPLEX', 'Escaped/code pipes may affect cell splitting; use the preserved raw table.', line=start+1)
            continue
        # Preserve each list item as its own unit; do not invent hierarchy from prose.
        is_list = markdown and re.match(r'^\s*(?:[-+*]|\d+[.)])\s+', line)
        i += 1
        if not is_list:
            while i < len(lines) and lines[i].strip():
                if markdown and (re.match(r'^\s*(?:#{1,6}\s|`{3,}|~{3,}|[-+*]\s|\d+[.)]\s)', lines[i]) or (i+1 < len(lines) and re.fullmatch(r'\s*(=+|-+)\s*', lines[i+1]))):
                    break
                i += 1
        value = '\n'.join(lines[start:i])
        item = block(doc, 'list_item' if is_list else 'paragraph', value, {'line_start': start+1, 'line_end': i}, links=text_links(value))
        for match in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', value):
            target = match[2].strip().strip('<>')
            image = {'alt': match[1], 'target': target, 'status': 'not_fetched'}
            if not re.match(r'^[a-zA-Z][\w+.-]*:', target):
                source = (path.parent / target).resolve()
                # Do not follow document-supplied paths outside its own folder.
                if path.parent.resolve() in source.parents and source.is_file() and source.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.gif') and source.stat().st_size <= MAX_INPUT:
                    output = assets / ('%s-%03d%s' % (doc['id'], len(doc['assets'])+1, source.suffix.lower()))
                    shutil.copy2(source, output)
                    image.update(path='assets/' + output.name, status='copied')
                    doc['assets'].append(image)
                else:
                    warning(doc, 'IMAGE_NOT_COPIED', 'Local Markdown image missing, outside source folder, too large, or unsupported.', block_id=item['id'])
            else:
                warning(doc, 'REMOTE_IMAGE_NOT_FETCHED', 'Remote Markdown image was not downloaded.', block_id=item['id'])
            item.setdefault('images', []).append(image)
    if markdown and re.search(r'<(?:table|img|iframe|script)\b', text, re.I):
        warning(doc, 'MARKDOWN_HTML_PRESERVED', 'Embedded HTML is preserved as text, not executed or interpreted.')


def docx_text(element):
    result = []
    def visit(node):
        if node.tag in (W+'del', W+'moveFrom'):
            return
        if node.tag == W+'t':
            result.append(node.text or '')
        elif node.tag == W+'tab':
            result.append('\t')
        elif node.tag in (W+'br', W+'cr'):
            result.append('\n')
        else:
            for child in node:
                visit(child)
    visit(element)
    return ''.join(result)


def extract_docx(path, doc, assets):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 6000 or sum(entry.file_size for entry in entries) > MAX_ZIP:
            raise InputProblem('DOCX archive exceeds decompression limit')
        names = set(archive.namelist())
        if 'word/document.xml' not in names:
            raise InputProblem('Not a supported DOCX package')
        main = xml(archive.read('word/document.xml'))
        styles = {}
        if 'word/styles.xml' in names:
            for style in xml(archive.read('word/styles.xml')).findall(W+'style'):
                outline = style.find('.//'+W+'outlineLvl')
                if outline is not None:
                    styles[style.get(W+'styleId')] = int(outline.get(W+'val', '0')) + 1
        media = {}
        for name in sorted(names):
            if name.startswith('word/media/') and not name.endswith('/'):
                suffix = Path(name).suffix.lower()
                if suffix not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.svg', '.emf', '.wmf'):
                    suffix = '.bin'
                output = assets / ('%s-%03d%s' % (doc['id'], len(doc['assets'])+1, suffix))
                output.write_bytes(archive.read(name))
                item = {'path': 'assets/'+output.name, 'original_member': name, 'status': 'extracted_not_interpreted'}
                media[name] = item['path']
                doc['assets'].append(item)
        def relationships(part):
            rel_path = str(Path(part).parent / '_rels' / (Path(part).name+'.rels'))
            if rel_path not in names:
                return {}
            return {node.get('Id'): {'target': node.get('Target',''), 'external': node.get('TargetMode')=='External'} for node in xml(archive.read(rel_path))}
        def read_part(part, root, role, xml_path=''):
            rels = relationships(part)
            paragraph_number = 0
            table_number = 0
            def paragraph(p, location):
                value = docx_text(p)
                style = p.find('./'+W+'pPr/'+W+'pStyle')
                style_name = style.get(W+'val','') if style is not None else ''
                direct = p.find('./'+W+'pPr/'+W+'outlineLvl')
                level = int(direct.get(W+'val','0'))+1 if direct is not None else styles.get(style_name)
                if not level:
                    match = re.match(r'(?:Heading|标题)\s*([1-6])$', style_name, re.I)
                    level = int(match[1]) if match else None
                links = []
                for h in p.findall('.//'+W+'hyperlink'):
                    rel = rels.get(h.get(R+'id'), {})
                    links.append({'label': docx_text(h), 'target': rel.get('target', '#'+h.get(W+'anchor',''))})
                images = []
                for node in p.iter():
                    rel_id = node.get(R+'embed') or node.get(R+'id')
                    if rel_id and node.tag.endswith(('}blip', '}imagedata')):
                        rel = rels.get(rel_id,{})
                        target = os.path.normpath(str(Path(part).parent / rel.get('target',''))).replace('\\','/')
                        images.append({'path': media.get(target), 'target': rel.get('target'), 'external': rel.get('external',False)})
                if value or images:
                    kind = 'heading' if level and level <= 6 else ('list_item' if p.find('./'+W+'pPr/'+W+'numPr') is not None else 'paragraph')
                    extras = {'role': role, 'links': links, 'images': images}
                    if kind == 'heading': extras['level'] = level
                    block(doc, kind if value else 'image', value, location, **extras)
                if p.find('.//'+W+'numPr') is not None:
                    warning(doc, 'DOCX_LIST_NUMBERING', 'List text preserved; generated numbering is not reconstructed.', **location)
            for node_index, node in enumerate(root,1):
                node_path=xml_path+'/'+node.tag.split('}')[-1]+'['+str(node_index)+']'
                if node.tag == W+'p':
                    paragraph_number += 1
                    paragraph(node, {'part': part, 'paragraph': paragraph_number, 'xml_path':node_path})
                elif node.tag == W+'tbl':
                    table_number += 1
                    rows, cells = [], []
                    for r_index, row in enumerate(node.findall(W+'tr'),1):
                        values = []
                        for c_index, cell in enumerate(row.findall(W+'tc'),1):
                            paras = cell.findall('.//'+W+'p')
                            value = '\n'.join(docx_text(p) for p in paras)
                            values.append(value)
                            cells.append({'row':r_index,'column':c_index,'text':value})
                        rows.append(values)
                    block(doc, 'table', '\n'.join('\t'.join(row) for row in rows), {'part':part,'table':table_number,'xml_path':node_path}, rows=rows, cells=cells, role=role)
                    if node.find('.//'+W+'gridSpan') is not None or node.find('.//'+W+'vMerge') is not None or node.find('./'+W+'tr/'+W+'tc/'+W+'tbl') is not None:
                        warning(doc,'DOCX_COMPLEX_TABLE','Merged/nested table: text retained; grid and merged-cell relationships need review.',part=part,table=table_number)
                    if any(x.tag.endswith('}blip') for x in node.iter()):
                        warning(doc,'DOCX_TABLE_IMAGE','Images in a table are retained in assets; association to cells needs review.',part=part,table=table_number)
                elif node.tag in (W+'sdt',W+'ins',W+'customXml',W+'moveTo'):
                    warning(doc,'DOCX_WRAPPED_CONTENT','Wrapped content was traversed; verify source order.',part=part)
                    inner = node.find(W+'sdtContent') if node.tag == W+'sdt' else node
                    if inner is not None: read_part(part,inner,role,node_path)
                elif node.tag not in (W+'sectPr',W+'bookmarkStart',W+'bookmarkEnd',W+'proofErr'):
                    if docx_text(node):
                        block(doc,'paragraph',docx_text(node),{'part':part,'element':node.tag.split('}')[-1],'xml_path':node_path},role=role)
                        warning(doc,'DOCX_UNMAPPED_ELEMENT','Text extracted from an unclassified element; verify placement.',part=part)
        body = main.find(W+'body')
        if body is None: raise InputProblem('DOCX has no document body')
        read_part('word/document.xml',body,'body')
        for part in sorted(names):
            if re.fullmatch(r'word/(?:header\d+|footer\d+)\.xml',part):
                read_part(part,xml(archive.read(part)),'header' if 'header' in part else 'footer')
            elif part in ('word/footnotes.xml','word/endnotes.xml','word/comments.xml'):
                root = xml(archive.read(part))
                for note_index,note in enumerate(root,1):
                    if note.get(W+'id','').startswith('-'): continue
                    read_part(part,note,'annotation','/note[%d;id=%s]'%(note_index,note.get(W+'id','')))
        if main.find('.//'+W+'txbxContent') is not None:
            warning(doc,'DOCX_TEXTBOX_ORDER','Text boxes are included in their anchor paragraphs, but visual reading order needs review.')
        if main.find('.//'+W+'del') is not None or main.find('.//'+W+'ins') is not None:
            warning(doc,'DOCX_TRACKED_CHANGES','Body text uses the current/final view: insertions included, deletions omitted. Revision history is not reconstructed.')
        if any('word/charts/' in name or 'word/embeddings/' in name for name in names):
            warning(doc,'DOCX_EMBEDDED_OBJECT','Embedded charts/objects were not interpreted.',severity='missing')
        if doc['assets']:
            warning(doc,'IMAGES_NOT_INTERPRETED','Images were extracted as assets; text in those images was not OCRed.',severity='review')
        doc['raw_text'] = '\n\n'.join(item['text'] for item in doc['blocks'])
        warning(doc,'DOCX_NO_PHYSICAL_PAGES','DOCX references use parts, paragraphs and tables; physical page numbers require a layout engine.')


def ocr_binary():
    if platform.system() != 'Darwin': return None
    arch = {'aarch64':'arm64','AMD64':'x86_64'}.get(platform.machine(),platform.machine())
    path = Path(__file__).resolve().parent / 'bin' / ('document-ocr-macos-'+arch)
    return path if path.is_file() and os.access(path,os.X_OK) else None


def run_ocr(path, page, doc, assets):
    executable = ocr_binary()
    if not executable:
        raise InputProblem('No compatible offline OCR binary. Run doctor; OCR capability was not installed automatically.')
    output = assets / ('%s-page-%04d.png' % (doc['id'],page))
    process = subprocess.run([str(executable),str(path),str(page),str(output)],capture_output=True,text=True,timeout=90)
    if process.returncode:
        raise InputProblem('Offline OCR failed: '+process.stderr.strip()[:300])
    result = json.loads(process.stdout)
    doc['assets'].append({'path':'assets/'+output.name,'page':page,'status':'page_render'})
    # Keep Vision order plus bounding boxes; do not guess the correct order of columns.
    lines = result.get('lines',[])
    for line_index, line in enumerate(lines,1):
        block(doc,'paragraph',line['text'],{'page':page,'ocr_line':line_index,'bbox':line['bbox'],'bbox_units':'normalized-top-left'},extraction='ocr',confidence=line['confidence'])
    warning(doc,'OCR_REVIEW_REQUIRED','OCR may misread names, digits and column order; verify against the retained page image.',page=page)
    if any(line['confidence'] < .75 for line in lines):
        warning(doc,'OCR_LOW_CONFIDENCE','Some recognized lines have confidence below 0.75.',severity='missing',page=page)
    return '\n'.join(line['text'] for line in lines)


def extract_pdf(path, doc, assets, ocr='auto', max_pages=500, password=None):
    from pypdf import PdfReader
    import logging
    class Capture(logging.Handler):
        def emit(self, record):
            warning(doc,'PDF_PARSER_WARNING',record.getMessage()[:500])
    logger = logging.getLogger('pypdf')
    capture = Capture()
    logger.addHandler(capture)
    try:
        reader = PdfReader(str(path),strict=False)
        if reader.is_encrypted and not reader.decrypt(password or ''):
            raise InputProblem('PDF is encrypted. Supply its password via --password-env; passwords are not saved in outputs.')
        total = len(reader.pages)
        doc['source']['page_count'] = total
        doc['pages'] = []
        if total > max_pages:
            warning(doc,'PAGE_LIMIT','Pages beyond --max-pages were not read.',severity='missing',page_start=max_pages+1,page_end=total)
        for number, page in enumerate(reader.pages[:max_pages],1):
            start = len(doc['blocks'])
            text = ''
            failure = None
            try:
                text = page.extract_text() or ''
            except Exception as error:
                failure = type(error).__name__
            compact = re.sub(r'\s','',text)
            images = 0
            try:
                resources = page.get('/Resources',{})
                resources = resources.get_object() if hasattr(resources,'get_object') else resources
                xobjects = resources.get('/XObject',{})
                xobjects = xobjects.get_object() if hasattr(xobjects,'get_object') else xobjects
                images = sum(obj.get_object().get('/Subtype') == '/Image' for obj in xobjects.values())
            except Exception:
                warning(doc,'PDF_IMAGE_INVENTORY','Could not enumerate page image objects.',page=number)
            needs_ocr = not compact or (len(compact)<30 and images>0) or failure is not None
            mode = 'text'
            if (needs_ocr and ocr=='auto') or ocr=='always':
                try:
                    recognized = run_ocr(path,number,doc,assets)
                    if recognized.strip():
                        text = recognized
                        mode = 'ocr'
                    else:
                        warning(doc,'EMPTY_OCR_RESULT','No text recognized. Page may be blank or unreadable; verify it.',severity='missing',page=number)
                except (InputProblem, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
                    warning(doc,'OCR_UNAVAILABLE',str(error),severity='missing',page=number)
            elif needs_ocr:
                warning(doc,'PAGE_NEEDS_OCR','No reliable text layer; OCR disabled. Page may be blank or scanned.',severity='missing',page=number)
            if mode=='text' and text.strip():
                # One block per paragraph; retain line breaks and page references.
                for index, value in enumerate(re.split(r'\n\s*\n',text),1):
                    if value.strip(): block(doc,'paragraph',value.strip(),{'page':number,'paragraph':index},extraction='text')
            if failure:
                warning(doc,'PDF_TEXT_EXTRACTION_FAILED','Text-layer extraction failed ('+failure+').',severity='review' if mode=='ocr' else 'missing',page=number)
            if '\ufffd' in text or text.count('\x00')>0:
                warning(doc,'PDF_GARBLED_TEXT','Text contains replacement/null characters; verify font mapping or use --ocr always.',severity='missing',page=number)
            if images and mode!='ocr':
                warning(doc,'PDF_IMAGE_CONTENT','Page contains image objects; text embedded in images may be absent. Use --ocr always if needed.',page=number)
            doc['pages'].append({'page':number,'method':mode,'text':text,'image_objects':images,'block_ids':[item['id'] for item in doc['blocks'][start:]],'status':'unresolved' if any(w.get('location',{}).get('page')==number and w['severity']=='missing' for w in doc['warnings']) else 'extracted'})
        doc['raw_text'] = '\n\n'.join('[Page %d]\n%s' % (page['page'],page['text']) for page in doc['pages'])
        warning(doc,'PDF_LAYOUT_REVIEW','PDF text order is not verified. Columns/tables remain page text, not reconstructed tables; OCR blocks include bounding boxes.')
    finally:
        logger.removeHandler(capture)


def extract_one(path, assets, encoding=None, ocr='auto', max_pages=500, password=None):
    path = Path(path).expanduser().resolve()
    doc = {'id':'d-'+hashlib.sha256(str(path).encode()).hexdigest()[:12], 'source':{'path':str(path),'name':path.name,'format':path.suffix.lower().lstrip('.')}, 'status':'error','blocks':[],'assets':[],'warnings':[],'raw_text':''}
    try:
        if not path.is_file(): raise InputProblem('Input file does not exist')
        if path.stat().st_size>MAX_INPUT: raise InputProblem('Input exceeds the 100 MiB size limit')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        doc['source'].update(sha256=digest,bytes=len(data))
        doc['id'] = 'd-'+hashlib.sha256((str(path)+digest).encode()).hexdigest()[:12]
        suffix = path.suffix.lower()
        if suffix in ('.txt','.md','.markdown'):
            extract_text_file(path,doc,assets,encoding)
        elif suffix=='.docx': extract_docx(path,doc,assets)
        elif suffix=='.pdf': extract_pdf(path,doc,assets,ocr,max_pages,password)
        elif suffix=='.doc': raise InputProblem('Legacy .doc is not .docx. Convert a copy to DOCX/PDF with Word or LibreOffice; no software was installed.')
        else: raise InputProblem('Unsupported format: '+suffix)
        if not doc['blocks']:
            warning(doc,'NO_CONTENT','No content was extracted; do not infer that the source has no information.',severity='missing')
        doc['status'] = 'partial' if any(w['severity']=='missing' for w in doc['warnings']) else 'extracted'
    except Exception as error:
        warning(doc,'EXTRACTION_ERROR',str(error)[:600],severity='error')
        doc['status'] = 'error'
    return doc
