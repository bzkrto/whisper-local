import sys,unittest,tempfile
from pathlib import Path
from datetime import datetime,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from whisper.tools.reminder_parser import parse_reminder
from whisper.common import TZ
from whisper.core.reasoning import AssistantLayers
class Tests(unittest.TestCase):
    def setUp(self):self.now=datetime(2026,10,4,21,10,tzinfo=TZ)
    def test_relative(self):
        r=parse_reminder('On dakika sonra bana hatırlat: Türkçe Çalış',self.now)
        self.assertEqual(r.due,self.now+timedelta(minutes=10));self.assertEqual(r.title,'Türkçe Çalış')
    def test_morning(self):
        r=parse_reminder('Yarın sabah saat onda bana hatırlat: toplantı',self.now)
        self.assertEqual(r.due,datetime(2026,10,5,10,tzinfo=TZ))
    def test_evening(self):
        r=parse_reminder('Yarın akşam sekizde bana hatırlat: çalış',self.now)
        self.assertEqual(r.due.hour,20)
    def test_legacy_numeric(self):
        r=parse_reminder('Yarın saat 10:00’da bana hatırlat: proje',self.now)
        self.assertEqual(r.due.hour,10)
    def test_ambiguous_no_write(self):
        with tempfile.TemporaryDirectory() as d:
            layers=AssistantLayers(Path(d)/'test.db')
            r=layers.intercept('Yarın saat onda bana hatırlat: proje',now=self.now)
            self.assertEqual(r['status'],'clarification');self.assertEqual(layers.store.tasks(),[])
    def test_invalid_and_past(self):
        for cmd in ('Bugün saat 20:00 bana hatırlat: proje','Yarın saat 25:00 bana hatırlat: proje','Sıfır dakika sonra hatırlat: proje','Yarın sabah saat onda hatırlat'):
            self.assertTrue(parse_reminder(cmd,self.now).error)
    def test_save_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.db';a=AssistantLayers(p)
            self.assertEqual(a.intercept('Bir dakika sonra bana hatırlat: ses testi',now=self.now)['source'],'KAYNAK_HAFIZA')
            b=AssistantLayers(p);rows=b.store.tasks();self.assertEqual(rows[0][1],'ses testi')
            self.assertEqual(datetime.fromisoformat(rows[0][2]).astimezone(TZ),self.now+timedelta(minutes=1))
    def test_unrelated_not_intercepted(self):self.assertIsNone(parse_reminder('Bugün saat kaç',self.now))
if __name__=='__main__':unittest.main()
