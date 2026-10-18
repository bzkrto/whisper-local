import sys,unittest,tempfile,json,subprocess,os
from pathlib import Path
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from whisper.core.reasoning import AssistantLayers
from whisper.memory.document_memory import DocumentMemory
from whisper.tools.pdf_worker import extract
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.a=AssistantLayers(self.root/'memory.db')
        self.d=DocumentMemory(self.a.store);self.p=self.root/'örnek.pdf';self.p.write_bytes(b'%PDF-1.7\nfixture')
    def tearDown(self):self.tmp.cleanup()
    def worker(self,*args,**kw):
        kw['stdout'].write(json.dumps({'page_count':3,'pages':[{'page':2,'text':'Karar değişimi sosyal çevreden etkilenebilir. Bu bir kaynak cümlesidir.'}]}).encode())
        return Mock(returncode=0)
    def ingest(self):
        with patch('whisper.memory.document_memory.subprocess.run',side_effect=self.worker):return self.d.ingest(str(self.p))
    def test_ingest_search_cites_actual_page_and_reopen(self):
        r=self.ingest();self.assertIn('1/3',r['response'])
        reopened=DocumentMemory(AssistantLayers(self.root/'memory.db').store)
        q=reopened.search('Karar değişimi');self.assertEqual(q['document_sources'][0]['page'],2)
        self.assertEqual(q['document_sources'][0]['name'],'örnek.pdf');self.assertIn('kaynak cümlesidir',q['response'])
    def test_duplicate_not_reparsed(self):
        self.ingest()
        with patch('whisper.memory.document_memory.subprocess.run') as worker:
            self.assertIn('zaten',self.d.ingest(str(self.p))['response']);worker.assert_not_called()
    def test_timeout_leaves_no_record(self):
        with patch('whisper.memory.document_memory.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',45)):
            with self.assertRaises(ValueError):self.d.ingest(str(self.p))
        self.assertIn('Kayıtlı PDF yok',self.d.intercept('Belgelerim')['response'])
    def test_scanned_no_fake_learning(self):
        def blank(*args,**kw):kw['stdout'].write(json.dumps({'page_count':1,'pages':[]}).encode())
        with patch('whisper.memory.document_memory.subprocess.run',side_effect=blank),self.assertRaises(ValueError):self.d.ingest(str(self.p))
        self.assertIn('Kayıtlı PDF yok',self.d.intercept('Belgelerim')['response'])
    def test_invalid_file_and_unmatched_query(self):
        self.p.write_bytes(b'not pdf')
        with self.assertRaises(ValueError):self.d.ingest(str(self.p))
        self.assertEqual(self.d.search('astronomi')['status'],'unverified')
    def test_forget_deletes_chunks_keeps_original(self):
        self.ingest();self.d.intercept('Belgeyi unut: 1')
        self.assertTrue(self.p.exists());self.assertEqual(self.d.search('Karar değişimi')['status'],'unverified')
    def test_export_real_file_with_page_sources(self):
        self.ingest();r=self.d.export_report('Karar değişimi')
        artifact=Path(r['artifact_path']);self.assertTrue(artifact.is_file());self.assertEqual(artifact.parent,self.root/'raporlar')
        self.assertIn('sayfa 2',artifact.read_text());self.assertIn('bağımsız doğrulama değildir',artifact.read_text())
    def test_extractor_preserves_sparse_page_numbers(self):
        reader=Mock(is_encrypted=False);reader.pages=[Mock(),Mock()]
        reader.pages[0].extract_text.return_value='';reader.pages[1].extract_text.return_value='source text'
        with patch('pypdf.PdfReader',return_value=reader):r=extract(str(self.p))
        self.assertEqual(r['pages'],[{'page':2,'text':'source text'}])
    def test_encrypted_rejected(self):
        with patch('pypdf.PdfReader',return_value=Mock(is_encrypted=True)),self.assertRaises(ValueError):extract(str(self.p))
    def test_real_pdf_worker_and_database(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        writer=PdfWriter();page=writer.add_blank_page(width=600,height=800)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        content=DecodedStreamObject();content.set_data(b'BT /F1 12 Tf 30 700 Td (Solar energy storage source.) Tj ET')
        page[NameObject('/Contents')]=writer._add_object(content)
        writer.write(self.p)
        r=self.d.ingest(str(self.p));self.assertEqual(r['status'],'success')
        q=self.d.search('Solar energy');self.assertEqual(q['document_sources'][0]['page'],1)
        self.assertIn('Solar energy storage',q['response'])
    def test_worker_ignores_legacy_console_encoding(self):
        env=dict(os.environ,PYTHONIOENCODING='cp1254')
        code="from whisper.tools import pdf_worker as w; w.extract=lambda path: {'page_count':1,'pages':[{'page':1,'text':path}]}; raise SystemExit(w.main())"
        text='Türkçe şğı — Ελληνικά 中文 😀'
        result=subprocess.run([sys.executable,'-c',code],input=json.dumps({'path':text},ensure_ascii=False).encode('utf-8'),
                              capture_output=True,cwd=str(ROOT),env=env,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['pages'][0]['text'],text)
    def test_missing_worker_reports_module_not_file_problem(self):
        def missing(*args,**kw):
            kw['stderr'].write(b'No module named whisper.tools.pdf_worker')
            return Mock(returncode=1)
        with patch('whisper.memory.document_memory.subprocess.run',side_effect=missing):
            r=self.d.intercept('PDF öğren: '+str(self.p))
        self.assertEqual(r['status'],'error');self.assertIn('modülü bulunamadı',r['response'])
        self.assertIn('Kayıtlı PDF yok',self.d.intercept('Belgelerim')['response'])
    def test_real_utf8_output_and_worker_flag(self):
        text='Türkçe bilgisi: ş ğ ı İ ç ö ü. 中文 😀'
        def worker(*args,**kw):
            self.assertEqual(args[0][1:3],['-X','utf8'])
            kw['stdout'].write(json.dumps({'page_count':1,'pages':[{'page':1,'text':text}]},ensure_ascii=False).encode('utf-8'))
            return Mock(returncode=0)
        with patch('whisper.memory.document_memory.subprocess.run',side_effect=worker):self.d.ingest(str(self.p))
        self.assertIn(text,self.d.search('Türkçe')['response'])
    def ingest_pages(self,pages):
        def worker(*args,**kw):
            kw['stdout'].write(json.dumps({'page_count':len(pages),'pages':[{'page':i,'text':t} for i,t in enumerate(pages,1)]}).encode())
            return Mock(returncode=0)
        with patch('whisper.memory.document_memory.subprocess.run',side_effect=worker):self.d.ingest(str(self.p))
    def test_article_number_preserved_and_heading_first(self):
        self.ingest_pages(['İçindekiler Madde 87 100 Madde 83 98',
                          'MADDE 83- Diğer konu.',
                          'MADDE 87- Aranan madde metni.',
                          'MADDE 870- Başka bir madde.'])
        result=self.d.search('MADDE 87')
        sources=result['document_sources']
        self.assertEqual(sources[0]['page'],3)
        self.assertNotIn(2,[x['page'] for x in sources])
        self.assertNotIn(4,[x['page'] for x in sources])
        self.assertEqual(self.d.search('MADDE 99')['status'],'unverified')
    def test_numbers_are_exact_search_terms(self):
        self.ingest_pages(['Model 87 ekran kartı.', 'Model 870 işlemci.'])
        self.assertEqual(self.d.search('87')['document_sources'][0]['page'],1)
        self.assertEqual(len(self.d.search('87')['document_sources']),1)
    def test_all_query_words_required(self):
        self.ingest_pages(['Karar değişimi sosyal çevreye bağlıdır.', 'Karar sadece bir kelimedir.'])
        result=self.d.search('Karar değişimi')
        self.assertEqual([s['page'] for s in result['document_sources']],[1])
    def test_document_receipt_preserves_sources(self):
        self.ingest();r=self.a.intercept('PDFde ara: Karar değişimi');self.a.record('PDFde ara: Karar değişimi',r)
        source=self.a.intercept('Bunu nereden biliyorsun');self.assertEqual(source['document_sources'][0]['page'],2)
if __name__=='__main__':unittest.main()
