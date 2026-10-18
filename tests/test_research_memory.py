import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from whisper.memory.research_memory import ResearchMemory, article_url, VisibleText

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'memory.db'
        self.store=ResearchMemory(self.path)
    def tearDown(self): self.tmp.cleanup()
    def test_same_source_content_deduplicates_across_access_times(self):
        a=self.store.capture('enerji','Kaynak bilgisi',[{'url':'https://arxiv.org/abs/1','retrieved_at':'a'}])
        b=self.store.capture('enerji','Kaynak bilgisi',[{'url':'https://arxiv.org/abs/1','retrieved_at':'b'}])
        self.assertEqual(a,b)
        row=self.store.find('enerji')[0]
        self.assertEqual(row['source_type'],'search_excerpt')
        self.assertEqual(row['sources'][0]['retrieved_at'],'b')
        reopened=ResearchMemory(self.path)
        self.assertEqual(reopened.find('enerji')[0]['id'],a)
    def test_literal_wildcards_do_not_match_every_source(self):
        self.store.capture('enerji','Bir kaynak',[{'url':'https://example.org'}])
        self.assertEqual(self.store.find('%'),[])
    def test_due_watch_is_claimed_once_and_disable_persists(self):
        with patch('whisper.memory.research_memory.time.time',return_value=100):
            wid=self.store.watch('Türkçe konuşma modelleri',24)
            self.assertEqual(self.store.due()[0],wid)
            self.assertIsNone(self.store.due())
            self.store.finish(wid,'error')
        with patch('whisper.memory.research_memory.time.time',return_value=100+86400):
            self.assertEqual(self.store.due()[0],wid)
            self.store.stop(wid)
        with patch('whisper.memory.research_memory.time.time',return_value=1e10):
            self.assertIsNone(ResearchMemory(self.path).due())
    def test_bad_watch_and_untrusted_urls_rejected(self):
        for hours in (0,1,True,169):
            with self.assertRaises(ValueError):self.store.watch('konu',hours)
        for url in ('http://arxiv.org/abs/1','https://arxiv.org.evil/abs/1','https://localhost/a',
                    'https://user@arxiv.org/abs/1','https://arxiv.org:8443/abs/1','https://arxiv.org/pdf/1'):
            with self.assertRaises(ValueError):article_url(url)
        self.assertEqual(article_url('https://arxiv.org/abs/1234.12345'),'https://arxiv.org/abs/1234.12345')
    def test_article_parser_discards_script_and_style_data(self):
        parser=VisibleText();parser.feed('<p>Makale</p><script>delete()</script><style>bad</style><p>Sonuç</p>')
        self.assertEqual(parser.parts,['Makale','Sonuç'])

if __name__=='__main__':unittest.main()
