import ast,json,sys,tempfile,typing,unittest,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from whisper.core.reasoning import AssistantLayers
from whisper.memory.document_memory import DocumentMemory
from whisper.memory.document_answer import answer_from_documents,parse_question,save_answer_report,quote_options

class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.layers=AssistantLayers(Path(self.tmp.name)/'memory.db')
        self.docs=DocumentMemory(self.layers.store)
        with self.layers.store.connect() as db:
            db.execute("INSERT INTO documents VALUES(1,'kitap.pdf','hash',251,250,'now')")
            for page in (67,202):
                text='MADDE 87- Meclisin görev ve yetkileri bu bölümde açıklanır.'
                db.execute('INSERT INTO document_chunks VALUES(?,?,?,?)',(1,page,text,text.lower()))
        self.request=self.docs.intercept('PDF sor: belge 1; sayfa 67; MADDE 87 ne anlatıyor?')
        self.llm=Mock(base_url='http://127.0.0.1:11434/v1',model='test-model')
        self.data={'answer':'Bu bölüm Meclisin görev ve yetkilerini anlatır.','insufficient':False,
                   'citations':[{'id':'S1','quote':'Meclisin görev ve yetkileri bu bölümde açıklanır.'}]}
        self.llm.chat.return_value=json.dumps(self.data,ensure_ascii=False)

    def test_scoped_retrieval_and_checked_sources(self):
        self.assertEqual(parse_question('belge 1; sayfa 67; MADDE 87 nedir?'),('MADDE 87 nedir?',1,67))
        self.assertEqual([s['page'] for s in self.request['document_sources']],[67])
        result=answer_from_documents(self.llm,self.request)
        self.assertEqual(result['status'],'success');self.assertFalse(result['answer_verified'])
        self.assertIn('kitap.pdf, sayfa 67',result['response'])
        payload=json.loads(self.llm.chat.call_args.args[1]);self.assertEqual(len(payload['sources']),1)

    def test_remote_disabled_even_when_cloud_allowed(self):
        self.llm.base_url='https://example.com/v1'
        self.assertEqual(answer_from_documents(self.llm,self.request)['status'],'clarification')
        self.llm.chat.assert_not_called()

    def test_fabricated_quote_or_page_rejected(self):
        for citation in ({'id':'S1','quote':'PDF içinde olmayan uydurma bir cümle'},
                         {'id':'S99','quote':self.data['citations'][0]['quote']}):
            self.data['citations']=[citation];self.llm.chat.return_value=json.dumps(self.data)
            self.assertEqual(answer_from_documents(self.llm,self.request)['status'],'unverified')

    def test_bad_json_action_claim_and_abstention(self):
        for data in ('bozuk JSON',json.dumps({'insufficient':True}),
                     json.dumps({**self.data,'answer':'Dosyayı açtım.'})):
            self.llm.chat.return_value=data
            self.assertNotEqual(answer_from_documents(self.llm,self.request)['status'],'success')

    def test_timeout_no_fabrication(self):
        self.llm.chat.side_effect=TimeoutError('timeout')
        self.assertEqual(answer_from_documents(self.llm,self.request)['status'],'error')

    def test_long_verbatim_quote_is_valid_but_invented_quote_is_not(self):
        text='MADDE 87- '+('Türkçe kaynak metni yalnız burada bulunur. '*15)
        request={**self.request,'document_sources':[
            {'document_id':1,'name':'kitap.pdf','page':202,'excerpt':text}]}
        self.data['citations']=[{'id':'S1','quote':text}]
        self.llm.chat.return_value=json.dumps(self.data)
        self.assertEqual(answer_from_documents(self.llm,request)['status'],'success')
        self.data['citations'][0]['quote']=text.replace('kaynak','uydurma',1)
        self.llm.chat.return_value=json.dumps(self.data)
        result=answer_from_documents(self.llm,request)
        self.assertEqual(result['status'],'unverified')
        self.assertIn('sayfa 202',result['response'])
        self.assertIn(text,result['response'])
        self.assertNotIn(self.data['answer'],result['response'])
        self.assertNotIn(text,result['spoken_response'])
        self.assertEqual(self.llm.chat.call_count,2)

    def test_invalid_quote_length_has_distinct_diagnostic(self):
        self.data['citations'][0]['quote']='x'*1201
        self.llm.chat.return_value=json.dumps(self.data)
        result=answer_from_documents(self.llm,self.request)
        self.assertEqual(result['status'],'unverified')
        self.assertIn('uzunluğu geçersiz',result['response'])
        self.assertNotIn('eşleşmedi',result['response'])

    def test_scoped_raw_search_never_calls_model(self):
        result=self.docs.intercept("PDF'de ara: belge 1; sayfa 202; MADDE 87")
        self.assertEqual(result['status'],'success')
        self.assertEqual([s['page'] for s in result['document_sources']],[202])
        self.assertNotIn('document_question',result)
        self.llm.chat.assert_not_called()

    def test_source_quote_selection_copies_original_text(self):
        self.data['citations']=[{'id':'S1','quote_id':'Q1'}]
        self.llm.chat.return_value=json.dumps(self.data)
        result=answer_from_documents(self.llm,self.request)
        self.assertEqual(result['status'],'success')
        expected=self.request['document_sources'][0]['excerpt']
        self.assertEqual(result['document_sources'][0]['quote'],expected)
        self.assertFalse(result['answer_verified'])
        payload=json.loads(self.llm.chat.call_args.args[1])
        self.assertEqual(payload['sources'][0]['quotes'][0]['text'],expected)
        self.assertEqual(self.llm.chat.call_count,1)

    def test_unknown_or_mixed_source_selection_is_rejected(self):
        for citation in ({'id':'S1','quote_id':'Q99'},
                         {'id':'S1','quote_id':['Q1']},
                         {'id':'S1','quote_id':'Q1','quote':'Uydurma cümle burada'}):
            self.data['citations']=[citation]
            self.llm.chat.return_value=json.dumps(self.data)
            result=answer_from_documents(self.llm,self.request)
            self.assertEqual(result['status'],'unverified')
            self.assertNotIn(self.data['answer'],result['response'])

    def test_quote_options_preserve_source_spans_and_bounds(self):
        for text in ('MADDE 87- '+('Türkçe şüphe öngörü kanun değişikliği. '*60),
                     'ş'*1200,'a'*349+' '+'b'*10):
            options=quote_options(text)
            self.assertTrue(options)
            self.assertTrue(all(15<=len(q)<=400 and q in text[:1200] for q in options.values()))
            self.assertEqual(''.join(''.join(options.values()).split()),
                             ''.join(text[:1200].split()))

    def test_no_match_no_generation_request(self):
        result=self.docs.intercept('PDF sor: belge 99; MADDE 87')
        self.assertNotIn('document_question',result);self.assertEqual(result['status'],'unverified')
        self.assertNotIn('document_question',self.docs.intercept("PDF'de ara: MADDE 87"))

    def test_source_query_exposes_actual_pages(self):
        result=answer_from_documents(self.llm,self.request)
        self.layers.record('PDF sor: MADDE 87',result)
        source=self.layers.intercept('Bu bilgiyi nereden öğrendin')
        self.assertIn('kitap.pdf, sayfa 67',source['response'])
        self.assertFalse(source['evidence']['answer_verified'])
        self.assertNotIn('kitap.pdf',source['spoken_response'])

    def test_report_persists_sources_and_utf8(self):
        self.layers.documents=self.docs
        request=self.layers.intercept('PDF cevap raporu: belge 1; sayfa 67; MADDE 87 ne anlatıyor?')
        result=save_answer_report(answer_from_documents(self.llm,request),self.layers.store.path)
        artifact=Path(result['artifact_path'])
        self.assertEqual(artifact.parent,Path(self.tmp.name)/'raporlar')
        body=artifact.read_text(encoding='utf-8')
        self.assertIn('MADDE 87 ne anlatıyor?',body)
        self.assertIn('kitap.pdf, sayfa 67',body)
        self.assertIn('bağımsız olarak doğrulanmadı',body)

    def test_failed_answers_never_saved_as_reports(self):
        result=save_answer_report({'status':'unverified','document_report_question':'soru'},self.layers.store.path)
        self.assertNotIn('artifact_path',result)
        self.assertFalse((Path(self.tmp.name)/'raporlar').exists())

    def test_report_write_error_and_no_overwrite(self):
        result=answer_from_documents(self.llm,self.request)
        result['document_report_question']='MADDE 87'
        with patch('whisper.memory.document_answer.uuid.uuid4',return_value=SimpleNamespace(hex='123456789012ab')):
            first=save_answer_report(result,self.layers.store.path)
            original=Path(first['artifact_path']).read_bytes()
            second=save_answer_report(result,self.layers.store.path)
        self.assertEqual(second['status'],'error');self.assertNotIn('artifact_path',second)
        self.assertEqual(Path(first['artifact_path']).read_bytes(),original)

    def test_brain_dispatch_speaks_answer_not_raw_chunks(self):
        import whisper_ses_v12 as core
        cfg=core.Config(db_path=str(self.layers.store.path),tts_engine='none',tools_enabled=True)
        with patch.object(core,'detect_backend',return_value=self.llm):
            instance=core.WhisperBrain(cfg)
        instance.layers.intercept=Mock(return_value=self.request)
        instance.voice=Mock()
        result=instance._process_command('PDF sor: MADDE 87')
        self.assertEqual(result['status'],'success')
        instance.voice.speak.assert_called_once_with(result['spoken_response'])
        self.assertNotIn('Kaynaklar:',result['spoken_response'])

if __name__=='__main__':unittest.main()
