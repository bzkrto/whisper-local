import ast,re,sys,typing,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from whisper.tools.volume_commands import volume_level
from whisper.common import fold
from computer_control import ComputerControl

class VolumeTests(unittest.TestCase):
    def test_natural_turkish_numbers(self):
        examples={'Ses seviyesine elliye getir.':50,
                  'Bilgisayarın sesini elliye getir.':50,
                  'Sesi yüzde elli yap':50,'Ses seviyesini 50 ayarla':50,
                  'Sesi 50’ye getir':50,'Sesi otuz beşe getir':35,
                  'Sesi dörde getir':4,'Ses seviyesini yüze getir':100,
                  'Sesi sıfıra indir':0,'Lütfen sesi yirmiye getir!':20}
        for command,value in examples.items():
            with self.subTest(command=command):self.assertEqual(volume_level(command),value)

    def test_noncommands_not_guessed(self):
        for command in ('YouTube sesini elliye getir','Sesi elliye getirme',
                        'Sesi elliye nasıl getiririm','Sesi yarıya getir',
                        'Sesi 50.5 yap','Bilgisayarın!','Sesi elliye getir ve dosyayı sil'):
            self.assertIsNone(volume_level(command),command)

    def test_direct_tool_dispatch_without_llm(self):
        core=ROOT/'whisper_ses_v12.py'
        if not core.exists():core=ROOT/'whisper_core.py'
        tree=ast.parse(core.read_text())
        cls=next(n for n in tree.body if getattr(n,'name','')=='ToolRunner')
        method=next(n for n in cls.body if getattr(n,'name','')=='direct_call')
        ns={'re':re,'Optional':typing.Optional,'normalize_tr':fold}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'tool','exec'),ns)
        self.assertEqual(ns['direct_call'](SimpleNamespace(),'Bilgisayarın sesini elliye getir.'),
                         'ses_ayarla|50')

    def test_relative_volume_aliases(self):
        for command in ('Sesi kıs','Sesini azalt','Sesi azalt'):
            self.assertEqual(ComputerControl.parse(command),('volume','volumedown'))
        self.assertIsNone(ComputerControl.parse('Sesi azaltma'))

    def test_windows_endpoint_receives_exact_percentage(self):
        core=ROOT/'whisper_ses_v12.py'
        if not core.exists():core=ROOT/'whisper_core.py'
        tree=ast.parse(core.read_text())
        cls=next(n for n in tree.body if getattr(n,'name','')=='ToolRunner')
        method=next(n for n in cls.body if getattr(n,'name','')=='_ses_ayarla')
        ns={'sys':SimpleNamespace(platform='win32')}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'tool','exec'),ns)
        volume=Mock();volume.GetMasterVolumeLevelScalar.return_value=0.5
        com=SimpleNamespace(CoInitialize=Mock(),CoUninitialize=Mock())
        audio=SimpleNamespace(GetSpeakers=Mock(return_value=SimpleNamespace(EndpointVolume=volume)))
        with patch.dict(sys.modules,{'comtypes':com,'pycaw':SimpleNamespace(),
                                    'pycaw.pycaw':SimpleNamespace(AudioUtilities=audio)}):
            self.assertIn('%50',ns['_ses_ayarla'](SimpleNamespace(),'50'))
            volume.SetMasterVolumeLevelScalar.assert_called_once_with(0.5,None)
            com.CoInitialize.assert_called_once();com.CoUninitialize.assert_called_once()
            volume.reset_mock()
            self.assertIn('0-100',ns['_ses_ayarla'](SimpleNamespace(),'101'))
            volume.SetMasterVolumeLevelScalar.assert_not_called()

if __name__=='__main__':unittest.main()
