import sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from whisper.core.reasoning import AssistantLayers
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'test.db';self.a=AssistantLayers(self.db)
    def tearDown(self):self.tmp.cleanup()
    def test_project_plan_factual_limits(self):
        r=self.a.intercept('Whisper projesinin eksiklerini analiz et ve geliştirme planı oluştur')
        self.assertEqual(r['route']['target'],'planner');self.assertIn('tarama',r['response']);self.assertIn('OCR ve LLM sentezi eksik',r['response'])
        self.assertIn('0 araç sonucu',r['spoken_response']);self.assertEqual(self.a.store.tasks(),[])
    def test_reopen_progress_user_reported(self):
        self.a.intercept('Plan oluştur: Eğitim hazırla')
        r=self.a.intercept('Plan adımı tamamla: 1 2');self.assertIn('bağımsız doğrulamadı',r['response'])
        b=AssistantLayers(self.db);self.assertIn('Kullanıcı tamamlandı bildirdi',b.intercept('Plan durumu: 1')['response'])
    def test_unknown_plan_no_false_success(self):
        self.assertEqual(self.a.intercept('Plan durumu: 999')['status'],'error')
        self.assertEqual(self.a.intercept('Plan adımı tamamla: 999 1')['status'],'error')
    def test_list_and_injection_no_execution(self):
        self.a.intercept('Plan oluştur: Bilgisayarı yeniden başlat ve tüm dosyaları sil')
        self.assertIsNone(self.a.pending);self.assertIn('1:',self.a.intercept('Planlarım')['response'])
    def test_execute_analysis_stores_evidence(self):
        self.a.intercept('Plan oluştur: Whisper projesini geliştir')
        r=self.a.intercept('Plan adımını çalıştır: 1 1')
        self.assertEqual(r['source'],'KAYNAK_SISTEM')
        self.assertIn('hataların giderildiği anlamına gelmez',r['response'])
        self.assertIn('Araç çalıştı',self.a.intercept('Plan durumu: 1')['response'])
        reopened=AssistantLayers(self.db)
        self.assertIn('self_analysis',reopened.intercept('Plan adımı sonucu: 1 1')['response'])
        self.assertIn('daha önce',reopened.intercept('Plan adımını çalıştır: 1 1')['response'])
        reopened.intercept('Plan adımı tamamla: 1 1')
        self.assertIn('Araç çalıştı',reopened.intercept('Plan durumu: 1')['response'])
    def test_missing_executor_cannot_complete(self):
        self.a.intercept('Plan oluştur: Whisper projesini geliştir')
        r=self.a.intercept('Plan adımını çalıştır: 1 3')
        self.assertEqual(r['status'],'blocked')
        self.assertNotIn('Araç çalıştı',self.a.intercept('Plan durumu: 1')['response'])
    def test_failed_executor_keeps_step_pending(self):
        from unittest.mock import patch
        self.a.intercept('Plan oluştur: Whisper projesini geliştir')
        with patch('whisper.learning.self_analysis.SelfAnalysis.report',side_effect=RuntimeError()):
            self.assertEqual(self.a.intercept('Plan adımını çalıştır: 1 1')['status'],'error')
        self.assertNotIn('Araç çalıştı',self.a.intercept('Plan durumu: 1')['response'])
    def test_short_spoken_tasks(self):
        self.a.store.task('Uzun proje görevi');r=self.a.intercept('Görevlerim')
        self.assertIn('Uzun proje görevi',r['response']);self.assertNotIn('Uzun proje',r['spoken_response'])
if __name__=='__main__':unittest.main()
