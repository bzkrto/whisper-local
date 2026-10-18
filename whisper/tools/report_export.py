"""Export saved WHISPER reports locally, without LLM calls or shell execution."""
from io import BytesIO
import os,re,uuid
import textwrap,zipfile
from xml.etree import ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape
from ..common import fold

REPORT_PATTERN=r'(?:pdf_(?:cevap|kaynak)|arastirma)_raporu_[a-f0-9]{12}\.md'

def report_names(database_path):
    directory=Path(database_path).resolve().parent/'raporlar'
    if directory.is_symlink() or getattr(directory,'is_junction',lambda:False)():
        raise ValueError('Rapor klasörü bağlantı olamaz.')
    if not directory.is_dir():return []
    files=[p for p in directory.iterdir() if re.fullmatch(REPORT_PATTERN,p.name)
           and p.is_file() and not p.is_symlink()]
    return [p.name for p in sorted(files,key=lambda p:(p.stat().st_mtime_ns,p.name),reverse=True)[:20]]

def slide_pages(text):
    question=next((s[6:].strip() for s in _lines(text) if s.startswith('Soru: ')),'Kaynaklı rapor')
    question_lines=textwrap.wrap(question,width=65)
    pages=[('PDF kaynaklı sunum',question_lines[:12])]
    for start in range(12,len(question_lines),12):pages.append(('Rapor sorusu',question_lines[start:start+12]))
    heading='Rapor içeriği';lines=[]
    def flush():
        for start in range(0,len(lines),12):pages.append((heading,lines[start:start+12]))
        lines.clear()
    for line in _lines(text):
        if not line.strip() or line.startswith(('# ','Soru: ')):continue
        if line=='Kaynaklar:':flush();heading='Kaynaklar';continue
        lines.extend(textwrap.wrap(line,width=70,replace_whitespace=False,drop_whitespace=True) or [''])
    flush()
    if len(pages)>30:raise ValueError('Sunum en fazla 30 slayt olabilir. Daha kısa bir rapor seçin.')
    return pages

def _pptx(text):
    """Create editable Open XML slides using a licensed blank Office template."""
    template=Path(__file__).parent/'assets'/'blank_presentation.pptx'
    with zipfile.ZipFile(template) as z:parts={name:z.read(name) for name in z.namelist()}
    p='http://schemas.openxmlformats.org/presentationml/2006/main'
    a='http://schemas.openxmlformats.org/drawingml/2006/main'
    r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    rel='http://schemas.openxmlformats.org/package/2006/relationships'
    ct='http://schemas.openxmlformats.org/package/2006/content-types'
    presentation=ET.fromstring(parts['ppt/presentation.xml'])
    size=presentation.find('{'+p+'}sldSz');size.set('cx','12192000');size.set('cy','6858000');size.set('type','screen16x9')
    ids=presentation.find('{'+p+'}sldIdLst')
    if ids is None:ids=ET.Element('{'+p+'}sldIdLst');presentation.insert(1,ids)
    relations=ET.fromstring(parts['ppt/_rels/presentation.xml.rels'])
    types=ET.fromstring(parts['[Content_Types].xml'])
    def box(id,title,lines,y,h,size):
        paragraphs=''.join('<a:p><a:pPr/><a:r><a:rPr lang="tr-TR" sz="'+str(size)+'" b="'+('1' if title else '0')+'"><a:solidFill><a:srgbClr val="111111"/></a:solidFill><a:latin typeface="Arial"/></a:rPr><a:t>'+escape(line)+'</a:t></a:r></a:p>' for line in lines)
        return f'<p:sp><p:nvSpPr><p:cNvPr id="{id}" name="Text {id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="731520" y="{y}"/><a:ext cx="10728960" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'
    for i,(title,lines) in enumerate(slide_pages(text),1):
        rid='rIdWhisper'+str(i)
        ET.SubElement(ids,'{'+p+'}sldId',{'id':str(255+i),'{'+r+'}id':rid})
        ET.SubElement(relations,'{'+rel+'}Relationship',{'Id':rid,'Type':r+'/slide','Target':f'slides/slide{i}.xml'})
        ET.SubElement(types,'{'+ct+'}Override',{'PartName':f'/ppt/slides/slide{i}.xml','ContentType':'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'})
        group='<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        parts[f'ppt/slides/slide{i}.xml']=(f'<p:sld xmlns:p="{p}" xmlns:a="{a}" xmlns:r="{r}"><p:cSld><p:spTree>'+group+box(2,True,[title],457200,914400,4200 if i==1 else 3200)+box(3,False,lines,1600200,4754880,2200)+'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>').encode('utf-8')
        parts[f'ppt/slides/_rels/slide{i}.xml.rels']=(f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="{r}/slideLayout" Target="../slideLayouts/slideLayout7.xml"/></Relationships>').encode()
    for prefix,uri in [('p',p),('a',a),('r',r)]:ET.register_namespace(prefix,uri)
    parts['ppt/presentation.xml']=ET.tostring(presentation,encoding='utf-8',xml_declaration=True)
    ET.register_namespace('',rel)
    parts['ppt/_rels/presentation.xml.rels']=ET.tostring(relations,encoding='utf-8',xml_declaration=True)
    ET.register_namespace('',ct)
    parts['[Content_Types].xml']=ET.tostring(types,encoding='utf-8',xml_declaration=True)
    app=ET.fromstring(parts['docProps/app.xml'])
    count=app.find('{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Slides')
    if count is not None:count.text=str(len(slide_pages(text)))
    parts['docProps/app.xml']=ET.tostring(app,encoding='utf-8',xml_declaration=True)
    out=BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    return out.getvalue()

def _lines(text):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text).splitlines()

def _word(text):
    from docx import Document
    from docx.shared import Inches,Pt,RGBColor
    from docx.oxml.ns import qn
    doc=Document();section=doc.sections[0]
    for style in doc.styles:
        for border in list(style.element.iter(qn('w:pBdr'))):
            border.getparent().remove(border)
    section.page_width=Inches(8.5);section.page_height=Inches(11)
    section.top_margin=section.bottom_margin=section.left_margin=section.right_margin=Inches(1)
    for name,size in [('Normal',11),('Title',18),('Heading 1',14),('Heading 2',12)]:
        style=doc.styles[name];style.font.name='Arial';style.font.size=Pt(size)
        style.font.color.rgb=RGBColor(0,0,0)
        style.paragraph_format.space_after=Pt(8)
    doc.styles['Normal'].paragraph_format.line_spacing=1.15
    for line in _lines(text):
        if not line.strip():continue
        if line.startswith('# '):doc.add_paragraph(line[2:],style='Title')
        elif line.startswith('## '):doc.add_paragraph(line[3:],style='Heading 1')
        elif line.strip()=='Kaynaklar:':doc.add_paragraph('Kaynaklar',style='Heading 2')
        else:doc.add_paragraph(line)
    doc.core_properties.title='Whisper kaynaklı rapor'
    doc.core_properties.author='Whisper'
    out=BytesIO();doc.save(out);return out.getvalue()

def _font_paths():
    fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    for normal,bold in [(fonts/'arial.ttf',fonts/'arialbd.ttf'),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))]:
        if normal.is_file() and bold.is_file():return normal,bold
    raise ValueError('Türkçe PDF için Arial yazı tipi bulunamadı. Windows Fonts klasörünü kontrol edin.')

def _pdf(text):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
    normal,bold=_font_paths()
    # One command at a time in the assistant; registration is reused locally.
    if 'WhisperRegular' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('WhisperRegular',str(normal)))
        pdfmetrics.registerFont(TTFont('WhisperBold',str(bold)))
    styles={
        'body':ParagraphStyle('body',fontName='WhisperRegular',fontSize=10.5,leading=15,spaceAfter=8),
        'title':ParagraphStyle('title',fontName='WhisperBold',fontSize=18,leading=24,spaceAfter=16,keepWithNext=True),
        'heading':ParagraphStyle('heading',fontName='WhisperBold',fontSize=12,leading=17,spaceBefore=10,spaceAfter=8,keepWithNext=True)}
    story=[]
    for line in _lines(text):
        if not line.strip():continue
        style='body'
        if line.startswith('# '):line=line[2:];style='title'
        elif line.startswith('## '):line=line[3:];style='heading'
        elif line.strip()=='Kaynaklar:':line='Kaynaklar';style='heading'
        story.append(Paragraph(escape(line),styles[style]))
    if not story:story=[Spacer(1,1)]
    out=BytesIO()
    SimpleDocTemplate(out,pagesize=letter,rightMargin=72,leftMargin=72,topMargin=72,bottomMargin=72,
                      title='Whisper kaynaklı rapor',author='Whisper').build(story)
    return out.getvalue()

def export_report(database_path,name,format):
    if format not in ('docx','pdf','pptx'):raise ValueError('Rapor biçimi Word, PDF veya PowerPoint olmalı.')
    name=name.strip().strip('"')
    if fold(name)=='son rapor':
        names=report_names(database_path)
        if not names:raise ValueError('Kayıtlı rapor yok. Önce PDF cevap raporu oluşturun.')
        name=names[0]
    if not re.fullmatch(REPORT_PATTERN,name):
        raise ValueError('Yalnız raporlar klasöründeki Whisper raporunun dosya adını yazın; tam yol kullanmayın.')
    directory=Path(database_path).resolve().parent/'raporlar'
    if directory.is_symlink() or getattr(directory,'is_junction',lambda:False)():
        raise ValueError('Rapor klasörü bağlantı olamaz.')
    source=directory/name
    if source.is_symlink() or getattr(source,'is_junction',lambda:False)() or not source.is_file():
        raise ValueError('Kayıtlı rapor dosyası bulunamadı.')
    if source.stat().st_size>250000:raise ValueError('Rapor dışa aktarma sınırı 250 KB.')
    raw=source.read_bytes()
    if len(raw)>250000:raise ValueError('Rapor dışa aktarma sınırı 250 KB.')
    text=raw.decode('utf-8-sig')
    try:data={'docx':_word,'pdf':_pdf,'pptx':_pptx}[format](text)
    except ImportError as exc:
        package='python-docx' if format=='docx' else 'reportlab'
        raise ValueError(f'{package} paketi eksik. PowerShell: .\\.venv\\Scripts\\python.exe -m pip install {package}') from exc
    destination=directory/(source.stem+'_'+uuid.uuid4().hex[:8]+'.'+format)
    created=False
    try:
        with destination.open('xb') as stream:
            created=True;stream.write(data)
    except OSError:
        if created:destination.unlink(missing_ok=True)
        raise
    return destination
