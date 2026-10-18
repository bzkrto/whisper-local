import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import os,zipfile
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from whisper.tools.report_export import export_report,report_names,slide_pages
from whisper.core.reasoning import AssistantLayers

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'raporlar';self.folder.mkdir()
        self.name='pdf_cevap_raporu_123456789abc.md';self.source=self.folder/self.name
        self.source.write_text('# PDF cevap raporu\n\nSoru: Türkçe harfler nasıl görünür?\n\n'
            'Çığ, öğüt, şüphe, İSTANBUL, ıslak. <img src="https://example.com">\n\n'
            'Kaynaklar:\n[S1] örnek.pdf, sayfa 67, belge 1\n'
            'Yerel model özeti; yorumun doğruluğu bağımsız olarak doğrulanmadı.\n',encoding='utf-8')

    def test_word_preserves_text_and_sources(self):
        from docx import Document
        output=export_report(self.root/'memory.db',self.name,'docx')
        text='\n'.join(p.text for p in Document(output).paragraphs)
        self.assertIn('Çığ, öğüt, şüphe, İSTANBUL, ıslak.',text)
        self.assertIn('örnek.pdf, sayfa 67',text)
        self.assertTrue(self.source.exists())

    def test_pdf_preserves_turkish_and_literal_markup(self):
        from pypdf import PdfReader
        output=export_report(self.root/'memory.db',self.name,'pdf')
        text='\n'.join(p.extract_text() for p in PdfReader(output).pages)
        self.assertIn('Çığ, öğüt, şüphe, İSTANBUL, ıslak.',text)
        self.assertIn('<img src="https://example.com">',text)
        self.assertIn('sayfa 67',text)

    def test_paths_and_symlinks_rejected(self):
        for name in ('../'+self.name,str(self.source),'other.md'):
            with self.assertRaises(ValueError):export_report(self.root/'memory.db',name,'pdf')
        self.source.unlink();self.source.symlink_to(self.root/'other.md')
        with self.assertRaises(ValueError):export_report(self.root/'memory.db',self.name,'pdf')

    def test_route_and_missing_package_no_false_success(self):
        layers=AssistantLayers(self.root/'memory.db')
        result=layers.intercept('Raporu Word yap: '+self.name)
        self.assertEqual(result['status'],'success');self.assertTrue(Path(result['artifact_path']).exists())
        with patch('whisper.tools.report_export._pdf',side_effect=ImportError('reportlab')):
            result=layers.intercept('Raporu PDF yap: '+self.name)
        self.assertEqual(result['status'],'error');self.assertNotIn('artifact_path',result)
        self.assertIn('pip install reportlab',result['response'])

    def test_latest_report_and_listing_use_saved_files(self):
        older=self.folder/'pdf_cevap_raporu_111111111111.md'
        older.write_text('Eski rapor');os.utime(older,(1,1))
        self.assertEqual(report_names(self.root/'memory.db')[0],self.name)
        layers=AssistantLayers(self.root/'memory.db')
        self.assertIn(self.name,layers.intercept('Raporlarım')['response'])
        result=layers.intercept('Raporu sunum yap: son rapor')
        self.assertEqual(result['status'],'success')
        self.assertTrue(Path(result['artifact_path']).is_file())

    def test_powerpoint_sources_editable_and_package_valid(self):
        output=export_report(self.root/'memory.db',self.name,'pptx')
        ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        texts=[]
        with zipfile.ZipFile(output) as z:
            self.assertIsNone(z.testzip())
            slides=[n for n in z.namelist() if __import__('re').fullmatch(r'ppt/slides/slide\d+\.xml',n)]
            self.assertEqual(len(slides),3)
            for n in slides:
                root=ET.fromstring(z.read(n));texts.extend(t.text for t in root.findall('.//a:t',ns))
            for n in z.namelist():
                if n.endswith(('.xml','.rels')):ET.fromstring(z.read(n))
        joined=' '.join(texts)
        self.assertIn('Çığ, öğüt, şüphe, İSTANBUL, ıslak.',joined)
        self.assertIn('örnek.pdf, sayfa 67',joined)
        self.assertIn('bağımsız olarak doğrulanmadı',joined)

    def test_long_slides_paginate_without_losing_words(self):
        text='# Rapor\nSoru: soru\n'+('Türkçe içerik ' * 300)+'\nKaynaklar:\nsayfa 67'
        pages=slide_pages(text);self.assertGreater(len(pages),3)
        self.assertTrue(all(len(lines)<=12 for title,lines in pages))
        all_text=' '.join(' '.join(lines) for title,lines in pages)
        self.assertEqual(all_text.count('Türkçe içerik'),300)

if __name__=='__main__':unittest.main()
