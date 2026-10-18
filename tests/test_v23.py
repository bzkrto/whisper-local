import base64
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from whisper.ai.router import ModelPool
from test_pipeline_regression import core

class RoleTests(unittest.TestCase):
    def setUp(self):
        self.names=['qwen3-vl:4b','qwen2.5-coder:7b','qwen3:8b']
        self.base=SimpleNamespace(model='qwen3:8b',name='Ollama',unload=Mock())
        self.factory=Mock(side_effect=lambda name:SimpleNamespace(model=name,name='Ollama',unload=Mock()))
        self.pool=ModelPool(self.base,lambda:self.names,self.factory,{'chat':'qwen3:8b','code':'qwen2.5-coder:7b','vision':'qwen3-vl:4b'})
    def test_installed_roles_release_only_on_switch(self):
        self.assertIs(self.pool.select('chat'),self.base);self.base.unload.assert_not_called()
        coder=self.pool.select('code');self.assertEqual(coder.model,'qwen2.5-coder:7b');self.base.unload.assert_called_once()
        self.assertIs(self.pool.select('code'),coder);coder.unload.assert_not_called()
        self.assertEqual(self.pool.select('vision').model,'qwen3-vl:4b');coder.unload.assert_called_once()
        self.assertIs(self.pool.select('chat'),self.base)
    def test_missing_vision_never_uses_text(self):
        self.names[:]=['qwen3:8b'];self.assertIsNone(self.pool.select('vision'));self.factory.assert_not_called()
        self.assertIs(self.pool.select('code'),self.base)
    def test_default_discovers_installed_models(self):
        pool=ModelPool(self.base,lambda:self.names,self.factory)
        self.assertEqual(pool.select('code').model,'qwen2.5-coder:7b')
        self.assertEqual(pool.select('vision').model,'qwen3-vl:4b')

class AdapterTests(unittest.TestCase):
    def make(self):
        return core.OllamaLLM('http://localhost:11434/v1','qwen3-vl:4b',api_key='local',temperature=.2,max_tokens=400,timeout=60,context=4096,name='Ollama')
    def response(self):
        r=Mock(status_code=200);r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False)
        r.json.return_value={'response':'Ekranda bir tarayıcı var.'};return r
    def test_native_image_payload(self):
        model=self.make()
        with patch.object(core.requests,'post',return_value=self.response()) as post:
            self.assertEqual(model.inspect_screen(b'jpeg','Ekranda ne var?'),'Ekranda bir tarayıcı var.')
        self.assertEqual(post.call_args.args[0],'http://localhost:11434/api/generate')
        p=post.call_args.kwargs['json'];self.assertEqual(p['images'],[base64.b64encode(b'jpeg').decode()])
        self.assertEqual(p['model'],'qwen3-vl:4b');self.assertFalse(p['stream'])
    def test_remote_is_blocked_before_network(self):
        model=self.make();model.base_url='https://external.example/v1'
        with patch.object(core.requests,'post') as post,self.assertRaises(core.LLMError):model.inspect_screen(b'jpeg','question')
        post.assert_not_called()
    def test_unload_selected_model(self):
        with patch.object(core.requests,'post',return_value=self.response()) as post:self.make().unload()
        self.assertEqual(post.call_args.kwargs['json'],{'model':'qwen3-vl:4b','keep_alive':0})
