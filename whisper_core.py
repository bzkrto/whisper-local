# -*- coding: utf-8 -*-
"""
JARVIS LOCAL — Yerel (offline) yapay zeka ile çalışan Türkçe sesli asistan.

Bulut yerine kendi bilgisayarındaki modeli kullanır:
  LLM : LM Studio / Ollama / llama.cpp  (OpenAI uyumlu /v1 API)  veya opsiyonel Gemini
  STT : faster-whisper (yerel) / Vosk (yerel) / Google (çevrimiçi)
  TTS : edge-tts (çevrimiçi, doğal ses) / Windows SAPI via pyttsx3 (yerel)

Hızlı başlangıç (LM Studio ile):
    lms server start
    lms get qwen/qwen3-4b-instruct-2507      # modeli indir (tek seferlik)
    python jarvis_local.py

Sunucu olmadan sadece mantığı test etmek için:
    python jarvis_local.py --say "Merhaba Jarvis, adım Ahmet" --tts none
    python jarvis_local.py --text
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import io
import json
import math
import os
import queue
import re
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import requests
import sounddevice as sd
import speech_recognition as sr

# Konsol UTF-8 (emoji/Türkçe karakterler için)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "whisper_memory.db"
TEMP_TTS_FILE = BASE_DIR / "temp_whisper_speech.mp3"


# ----------------------------------------------------------------------------
# AYARLAR
# ----------------------------------------------------------------------------
@dataclass
class Config:
    # LLM
    backend: str = "auto"                      # auto | lmstudio | ollama | llamacpp | gemini
    base_url: Optional[str] = None             # None -> otomatik bulunur
    model: Optional[str] = None                # None -> sunucudaki ilk sohbet modeli
    api_key: str = "lm-studio"                 # yerel sunucular anahtar istemez
    gemini_api_key: str = ""                   # backend=gemini ise gerekir
    temperature: float = 0.7
    max_tokens: int = 400
    request_timeout: int = 300                 # ilk yükleme (model RAM'e alınması) uzun sürebilir
    auto_start_server: bool = False            # sunucu kapalıysa `lms server start` ile aç

    # Konuşma
    tts_engine: str = "auto"                   # auto | edge | sapi | none
    stt_engine: str = "auto"                   # auto | whisper | vosk | google
    language: str = "tr"
    # Ses: çok dilli yeni nesil sesler Türkçeyi daha doğal okur (Ahmet/Emel = yerli, daha hızlı üretim)
    # Ölçüm: Florian 1,0-1,2 sn'de hazır oluyor (Ahmet 0,75-1,04) ama çok daha doğal ses.
    voice: str = "de-DE-FlorianMultilingualNeural"
    voice_rate: str = "+18%"                  # konuşma hızı ("+18%" daha akıcı/çevik)
    voice_pitch: str = "+0Hz"                 # ton ("-16Hz" boğuk ve robotik duruyordu)
    tts_sentence_stream: bool = True          # yanıtı cümle cümle üretip hemen okumaya başla
    whisper_model: str = "small"               # tiny | base | small | medium | large-v3
    # "cpu": Whisper işlemcide çalışır, ekran kartını tamamen LLM'e bırakır (8 GB VRAM için önerilir).
    # "cuda": daha hızlı tanıma ama VRAM'i LLM ile paylaşır (büyük modellerde taşmaya yol açar).
    # "auto": GPU'da yer var mı diye bakmadan CUDA'yı dener.
    whisper_device: str = "cpu"                # auto | cuda | cpu
    # Whisper'a verilen ön ipucu: özel isimlerin (Jarvis, RTX...) doğru yazılmasına yardım eder
    whisper_prompt: str = (
        "Jarvis adlı Türkçe sesli asistanla konuşma. Ekran kartı, bilgisayar, RTX, "
        "model, yazılım gibi teknik kelimeler geçer."
    )
    whisper_beam: int = 5                      # 5 = daha doğru, 1 = en hızlı
    vosk_model_dir: str = "vosk-model-small-tr"
    input_device: Optional[int] = None         # None -> ses veren cihaz otomatik bulunur
    input_samplerate: Optional[int] = None     # None -> cihazın varsayılan frekansı
    input_exclusive: bool = False              # WASAPI özel mod (bazı mikrofonlar sadece böyle çalışır)
    max_record_seconds: int = 15
    silence_seconds: float = 0.8               # bu kadar sessizlik olunca kaydı bitir (kısa = hızlı sıra)
    exit_words: tuple = ("çıkış", "kapat", "dur", "iptal", "kapan", "görüşürüz")

    # İnternet ve hızlı görevler
    internet: bool = True                      # internet araması açık mı
    default_city: str = "İstanbul"             # hava durumu için varsayılan şehir
    llm_context: int = 8192                    # modeli yüklerken bağlam (büyük bağlam GPU'yu taşırır)

    # Dosyalar
    db_path: str = str(DB_PATH)

    extra_body: Dict[str, Any] = field(default_factory=dict)  # modele özel ek JSON alanları


# ----------------------------------------------------------------------------
# HAFIZA
# ----------------------------------------------------------------------------
# Bilgi karşılaştırmasında yoksayılan dolgu kelimeleri
STOPWORDS = {
    "ve", "bir", "var", "yok", "ile", "ise", "de", "da", "ki", "bu", "şu", "o", "ben", "benim",
    "bana", "benimle", "kullanıcı", "kullanıcının", "kullanıcıya", "bilgi", "bilgisi", "ayrıca",
    "olarak", "sahip", "olan", "olduğu", "onun", "istiyor", "seviyor", "adında", "isminde",
    "the", "and", "is", "user",
}


class MemoryEngine:
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_command TEXT,
                response TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT UNIQUE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        self._init_cache()

    def save_interaction(self, user_command: str, response: str):
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT INTO conversation_history (user_command, response) VALUES (?, ?)",
                (user_command, response),
            )
            conn.commit()
        finally:
            conn.close()

    def all_facts(self) -> List[str]:
        conn = self._get_connection()
        try:
            return [r[0] for r in conn.execute("SELECT fact FROM user_profile").fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _normalize(fact: str) -> set:
        tokens = re.findall(r"\w+", fact.lower())
        return {t for t in tokens if t not in STOPWORDS}

    @staticmethod
    def _same_token(a: str, b: str) -> bool:
        """Basit Türkçe ek toleransı: 'kedi' ~ 'kedisi'."""
        if a == b:
            return True
        n = min(len(a), len(b))
        return n >= 4 and a[:n] == b[:n]

    def _already_known(self, new_tokens: set, existing_sets: List[set]) -> bool:
        union: set = set()
        for old in existing_sets:
            union |= old
            if not new_tokens or not old:
                continue
            overlap = len(new_tokens & old) / len(new_tokens | old)
            if overlap >= 0.5:                      # neredeyse aynı bilgi
                return True
        # yeni bilginin tamamı bilinen kelimelerden oluşuyorsa: yeni bir şey yok
        if new_tokens and all(any(self._same_token(t, u) for u in union) for t in new_tokens):
            return True
        return False

    def save_fact(self, fact: str) -> bool:
        """Yeni bilgiyi kaydeder; benzeri zaten varsa yoksayar."""
        fact = (fact or "").strip()
        if len(fact) < 3:
            return False

        new_tokens = self._normalize(fact)
        existing_sets = [self._normalize(f) for f in self.all_facts()]
        if self._already_known(new_tokens, existing_sets):
            return False

        conn = self._get_connection()
        try:
            conn.execute("INSERT OR IGNORE INTO user_profile (fact) VALUES (?)", (fact,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def get_user_profile(self) -> str:
        conn = self._get_connection()
        try:
            rows = conn.execute("SELECT fact FROM user_profile").fetchall()
        finally:
            conn.close()
        if not rows:
            return "Henüz kullanıcı hakkında özel bir kayıt yok."
        return "\n".join(f"- {r[0]}" for r in rows)

    # -- önbellek: aynı soru tekrar sorulursa model/GPU kullanılmadan yanıtlanır
    def _init_cache(self):
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    kind TEXT,
                    expires REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def cache_get(self, key: str) -> Optional[str]:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT value, expires FROM cache WHERE key = ?", (key,)).fetchone()
        except sqlite3.OperationalError:
            self._init_cache()
            return None
        finally:
            conn.close()
        if not row:
            return None
        value, expires = row
        if expires and expires < time.time():
            self.cache_delete(key)
            return None
        return value

    def cache_set(self, key: str, value: str, ttl_seconds: int, kind: str = "genel"):
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, kind, expires) VALUES (?, ?, ?, ?)",
                (key, value, kind, time.time() + ttl_seconds),
            )
            conn.commit()
        except sqlite3.OperationalError:
            self._init_cache()
        finally:
            conn.close()

    def cache_delete(self, key: str):
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    def cache_summary(self, limit: int = 10) -> List[tuple]:
        conn = self._get_connection()
        try:
            return conn.execute(
                "SELECT key, kind FROM cache WHERE expires > ? ORDER BY timestamp DESC LIMIT ?",
                (time.time(), limit),
            ).fetchall()
        except Exception:
            return []
        finally:
            conn.close()

    def recent_history(self, limit: int = 6) -> List[tuple]:
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT user_command, response FROM conversation_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
        return list(reversed(rows))


# ----------------------------------------------------------------------------
# LLM ARKA UÇLARI (yerel, OpenAI uyumlu)
# ----------------------------------------------------------------------------
LOCAL_BACKENDS = (
    ("lmstudio", "http://127.0.0.1:1234/v1", "LM Studio"),
    ("ollama", "http://127.0.0.1:11434/v1", "Ollama"),
    ("llamacpp", "http://127.0.0.1:8080/v1", "llama.cpp"),
)

SERVER_HELP = """\
⚠️  Yerel yapay zeka sunucusu bulunamadı.

  LM Studio ile (önerilen, bu bilgisayarda kurulu):
      lms server start
      lms get qwen/qwen3-4b-instruct-2507      # veya: lms get google/gemma-3-4b
      python jarvis_local.py

  Ollama ile:
      ollama serve
      ollama pull qwen3:4b

  Sunucu zaten açıksa adresi elle ver:
      python jarvis_local.py --base-url http://127.0.0.1:1234/v1 --model model-adi
"""


class LLMError(RuntimeError):
    pass


class OpenAICompatLLM:
    """LM Studio / Ollama / llama.cpp / herhangi bir OpenAI uyumlu yerel sunucu."""

    def __init__(self, base_url: str, model: str, api_key: str = "lm-studio",
                 temperature: float = 0.7, max_tokens: int = 400,
                 timeout: int = 300, extra_body: Optional[Dict[str, Any]] = None,
                 name: str = "yerel"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra_body = extra_body or {}
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    @staticmethod
    def list_models(base_url: str, api_key: str = "lm-studio", timeout: float = 2.0) -> List[str]:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        r = requests.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return [m.get("id", "") for m in data.get("data", [])]

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        payload.update(self.extra_body)

        last_err: Optional[Exception] = None
        for attempt in range(2):
            try:
                r = requests.post(f"{self.base_url}/chat/completions", json=payload,
                                  headers=self.headers, timeout=self.timeout)
                if r.status_code >= 400:
                    raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
                data = r.json()
                return data["choices"][0]["message"]["content"] or ""
            except Exception as e:      # ağ / model yükleme hataları
                last_err = e
                if attempt == 0:
                    print(f"   ↻ Model yükleniyor olabilir, tekrar deneniyor... ({type(e).__name__})")
                    time.sleep(2)
        raise LLMError(str(last_err))

    def chat_stream(self, system_prompt: str, user_prompt: str):
        """Yanıtı parça parça (token token) üretir — ilk ses için bekleme süresini kısaltır."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        payload.update(self.extra_body)
        r = requests.post(f"{self.base_url}/chat/completions", json=payload,
                          headers=self.headers, stream=True, timeout=self.timeout)
        if r.status_code >= 400:
            raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
        # DİKKAT: decode_unicode=True yanlış kodlama seçip Türkçe karakterleri bozuyor.
        # Bu yüzden baytları kendimiz UTF-8 olarak çözüyoruz.
        for raw in r.iter_lines(decode_unicode=False):
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
            except Exception:
                continue
            if delta:
                yield delta


class GeminiLLM:
    """Opsiyonel bulut yedeği (kodunuzdaki eski davranış)."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash",
                 temperature: float = 0.7, **_: Any):
        from google import genai  # tembel import
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.name = "gemini"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        resp = self.client.models.generate_content(
            model=self.model,
            contents=f"{system_prompt}\n\nKullanıcı Cümlesi: \"{user_prompt}\"",
        )
        return resp.text or ""

    def chat_stream(self, system_prompt: str, user_prompt: str):
        yield self.chat(system_prompt, user_prompt)      # Gemini tarafında akış yok


# Sunucunun listelediği ama sohbet için kullanılamayan modeller (embedding, ses, görüntü...)
NON_CHAT_HINTS = (
    "embed", "rerank", "whisper", "clip", "tts", "speech", "voice", "voxtral", "kokoro",
    "piper", "audio", "music", "stable-diffusion", "flux", "bge", "gte", "e5-", "sentence",
)


def _is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    return not any(k in low for k in NON_CHAT_HINTS)


def _default_extra_body(model_id: str) -> Dict[str, Any]:
    """Qwen3 'düşünen' modelleri sesli asistan için çok yavaş; düşünmeyi kapat."""
    if "qwen3" in model_id.lower():
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}


def try_start_lmstudio_server() -> bool:
    """LM Studio sunucusu kapalıysa `lms server start` ile açar."""
    exe = Path.home() / ".lmstudio" / "bin" / "lms.exe"
    if not exe.exists():
        print(f"   (lms.exe bulunamadı: {exe})")
        return False
    print("⏳ LM Studio sunucusu başlatılıyor...")
    try:
        subprocess.run([str(exe), "server", "start"], capture_output=True, text=True, timeout=60)
    except Exception as e:
        print(f"   başlatılamadı: {e}")
        return False
    time.sleep(3)
    return True


def ensure_lmstudio_model(model: str, context: int = 8192, parallel: int = 1) -> bool:
    """LM Studio'da model yüklü değilse makul bağlamla yükler.

    Model API isteğiyle kendiliğinden yüklenirse çok büyük bağlam seçip ekran kartını
    taşırabiliyor; bu yüzden bağlamı biz belirliyoruz.
    """
    exe = Path.home() / ".lmstudio" / "bin" / "lms.exe"
    if not exe.exists() or not model:
        return False
    try:
        out = subprocess.run([str(exe), "ps"], capture_output=True, text=True, timeout=25).stdout
        anahtar = model.split("/")[-1].lower()
        if any(anahtar in satir.lower() for satir in out.splitlines()):
            return False                       # zaten yüklü: dokunma
        print(f"⏳ Model '{model}' {context} bağlamla yükleniyor (ekran kartı taşmasın)...")
        subprocess.run([str(exe), "load", model, "-c", str(context),
                        "--parallel", str(parallel), "-y"],
                       capture_output=True, text=True, timeout=900)
        return True
    except Exception as e:
        print(f"   ⚠️  Model yüklenemedi: {type(e).__name__}")
        return False


def _scan_backends(cfg: Config, candidates, errors: List[str]) -> Optional[OpenAICompatLLM]:
    for key, url, label in candidates:
        try:
            models = OpenAICompatLLM.list_models(url, cfg.api_key)
        except Exception as e:
            errors.append(f"   - {label} ({url}): {type(e).__name__}")
            continue

        chat_models = [m for m in models if _is_chat_model(m)]
        if cfg.model:
            model = cfg.model
        elif chat_models:
            model = chat_models[0]
        else:
            errors.append(f"   - {label} ({url}): çalışıyor ama sohbet modeli yok "
                          f"(sadece embedding?): {models}")
            continue

        if not cfg.extra_body:
            cfg.extra_body = _default_extra_body(model)

        print(f"✅ Yerel LLM: {label}  |  adres: {url}  |  model: {model}")
        if len(chat_models) > 1:
            print(f"   (sunucudaki diğer modeller: {', '.join(chat_models[1:4])}"
                  f"{' ...' if len(chat_models) > 4 else ''})")
        return OpenAICompatLLM(
            base_url=url, model=model, api_key=cfg.api_key,
            temperature=cfg.temperature, max_tokens=cfg.max_tokens,
            timeout=cfg.request_timeout, extra_body=cfg.extra_body, name=label,
        )
    return None


def detect_backend(cfg: Config, required: bool = True) -> Optional[OpenAICompatLLM]:
    """Sırayla LM Studio -> Ollama -> llama.cpp dener, ilk ayakta olanı seçer.

    required=False ise sunucu yoksa hata vermez, None döndürür (hızlı görevler çalışsın).
    """
    candidates = LOCAL_BACKENDS
    if cfg.backend not in ("auto", "gemini"):
        candidates = tuple(c for c in LOCAL_BACKENDS if c[0] == cfg.backend) or LOCAL_BACKENDS
    if cfg.base_url:
        candidates = ((cfg.backend if cfg.backend != "auto" else "custom", cfg.base_url, "özel sunucu"),)

    errors: List[str] = []
    llm = _scan_backends(cfg, candidates, errors)

    if llm is None and cfg.auto_start_server and not cfg.base_url:
        if try_start_lmstudio_server():
            errors = []
            llm = _scan_backends(cfg, candidates, errors)
    if llm is not None:
        return llm

    if not required:
        return None

    print(SERVER_HELP)
    if errors:
        print("Denenen adresler:")
        print("\n".join(errors))
    raise SystemExit(1)


# ----------------------------------------------------------------------------
# KONUŞMA TANIMA (STT)
# ----------------------------------------------------------------------------
def _prepare_cuda_dlls() -> None:
    """LM Studio'nun getirdiği CUDA DLL'lerini (cuBLAS/cuDART) bulunabilir yap."""
    vendor = Path.home() / ".lmstudio" / "extensions" / "backends" / "vendor"
    if not vendor.exists():
        return
    for dll in vendor.rglob("cublas64_12.dll"):
        d = str(dll.parent)
        try:
            os.add_dll_directory(d)
        except Exception:
            pass
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


class WhisperSTT:
    """faster-whisper ile tamamen yerel, GPU/CPU üzerinde çalışan STT."""

    name = "faster-whisper"

    def __init__(self, model_size: str = "small", device: str = "auto", language: str = "tr",
                 initial_prompt: str = "", beam_size: int = 5):
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from faster_whisper import WhisperModel  # pip install faster-whisper

        if device == "auto":
            free = free_vram_mb()
            try:
                import ctranslate2
                has_cuda = ctranslate2.get_cuda_device_count() > 0
            except Exception:
                has_cuda = False
            if has_cuda and (free is None or free >= 2500):
                device = "cuda"          # GPU'da yeterli boş yer var
            elif has_cuda:
                print(f"ℹ️  Ekran kartında yeterli boş yer yok ({free} MB) -> Whisper işlemcide çalışacak.")
                device = "cpu"
            else:
                device = "cpu"
        if device == "cuda":
            _prepare_cuda_dlls()

        compute_type = "int8_float16" if device == "cuda" else "int8"
        print(f"🧠 Whisper '{model_size}' yükleniyor ({device}/{compute_type}) — ilk seferde indirilebilir...")
        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as e:
            if device != "cuda":
                raise
            # cuDNN/cuBLAS eksikse GPU başlatılamaz -> CPU'ya düş
            print(f"⚠️  GPU üzerinde başlatılamadı ({type(e).__name__}: {e})")
            print("   CPU (int8) ile devam ediliyor. GPU hızı için: python -m pip install nvidia-cudnn-cu12")
            device, compute_type = "cpu", "int8"
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.device = device
        self.language = language
        self.initial_prompt = initial_prompt or None
        self.beam_size = beam_size
        print(f"✅ Yerel konuşma tanıma hazır ({device}, beam={beam_size}).")

    def transcribe(self, audio_int16: np.ndarray, samplerate: int = 16000) -> str:
        # Kısık kaydı yükselt: Whisper sessiz sesi belirgin şekilde kötü anlıyor
        audio_int16 = normalize_int16(audio_int16)
        audio = audio_int16.astype(np.float32) / 32768.0
        segments, _info = self.model.transcribe(
            audio, language=self.language, beam_size=self.beam_size, vad_filter=True,
            condition_on_previous_text=False, initial_prompt=self.initial_prompt,
        )
        return " ".join(s.text.strip() for s in segments).strip()


class VoskSTT:
    name = "vosk"

    def __init__(self, model_dir: str = "vosk-model-small-tr"):
        from vosk import Model, KaldiRecognizer  # pip install vosk
        self._KaldiRecognizer = KaldiRecognizer
        self.model = Model(model_dir)

    def transcribe(self, audio_int16: np.ndarray, samplerate: int = 16000) -> str:
        rec = self._KaldiRecognizer(self.model, samplerate)
        rec.AcceptWaveform(audio_int16.tobytes())
        return json.loads(rec.FinalResult()).get("text", "").strip()


class GoogleSTT:
    """Çevrimdışı değildir ama kurulum gerektirmez (ücretsiz web API)."""

    name = "google (çevrimiçi)"

    def __init__(self, language: str = "tr"):
        self.recognizer = sr.Recognizer()
        self.lang_code = "tr-TR" if language.startswith("tr") else language

    def transcribe(self, audio_int16: np.ndarray, samplerate: int = 16000) -> str:
        wav_io = io.BytesIO()
        import scipy.io.wavfile as wav
        wav.write(wav_io, samplerate, audio_int16)
        wav_io.seek(0)
        with sr.AudioFile(wav_io) as source:
            audio = self.recognizer.record(source)
        try:
            return self.recognizer.recognize_google(audio, language=self.lang_code)
        except sr.UnknownValueError:
            return ""


def build_stt(cfg: Config):
    order = ["whisper", "vosk", "google"] if cfg.stt_engine == "auto" else [cfg.stt_engine]
    for engine in order:
        try:
            if engine == "whisper":
                return WhisperSTT(cfg.whisper_model, cfg.whisper_device, cfg.language,
                                  cfg.whisper_prompt, cfg.whisper_beam)
            if engine == "vosk":
                return VoskSTT(cfg.vosk_model_dir)
            if engine == "google":
                return GoogleSTT(cfg.language)
        except ImportError as e:
            if cfg.stt_engine != "auto":
                print(f"⚠️  '{engine}' kurulu değil: {e}")
                print("   Yerel STT için:  python -m pip install faster-whisper")
            continue
        except Exception as e:
            print(f"⚠️  '{engine}' başlatılamadı: {e}")
            continue
    raise SystemExit("❌ Kullanılabilir konuşma tanıma motoru yok. 'python -m pip install faster-whisper' deneyin.")


# ----------------------------------------------------------------------------
# SESLENDİRME (TTS)
# ----------------------------------------------------------------------------
class EdgeTTS:
    name = "edge-tts (çevrimiçi)"

    def __init__(self, voice: str = "de-DE-FlorianMultilingualNeural",
                 rate: str = "+18%", pitch: str = "+0Hz"):
        import edge_tts  # noqa: F401
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def _generate(self, text: str, output_file: str):
        import edge_tts
        communicate = edge_tts.Communicate(text, self.voice, pitch=self.pitch, rate=self.rate)
        await communicate.save(output_file)

    @staticmethod
    def _play_native(abs_path: str):
        winmm = ctypes.windll.winmm
        winmm.mciSendStringW("close whisper_sound", None, 0, 0)
        winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias whisper_sound', None, 0, 0)
        winmm.mciSendStringW("play whisper_sound wait", None, 0, 0)
        winmm.mciSendStringW("close whisper_sound", None, 0, 0)

    def speak(self, text: str) -> bool:
        if not is_speakable(text):
            return True                      # okunacak harf yok (sadece emoji/simge)
        tmp = str(TEMP_TTS_FILE)
        try:
            for deneme in range(3):          # anlık ağ/rate-limit hatalarına karşı yeniden dene
                try:
                    asyncio.run(self._generate(text, tmp))
                    if os.path.exists(tmp) and os.path.getsize(tmp) > 1024:
                        self._play_native(tmp)
                        return True
                    print(f"   ⚠️  Ses boş geldi, tekrar deneniyor ({deneme + 1}/3)")
                except Exception as e:
                    print(f"   ⚠️  edge-tts hatası ({deneme + 1}/3) metin={text[:45]!r}: {str(e)[:50]}")
                time.sleep(0.4)
            return False
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass


class GoogleTranslateTTS:
    """gTTS: Google'ın yerli Türkçe sesi (ücretsiz, internet gerektirir, hız ayarı yok)."""

    name = "gTTS (yerli Türkçe)"

    def __init__(self, lang: str = "tr", tld: str = "com.tr", slow: bool = False):
        import gtts  # noqa: F401    # pip install gTTS
        self.lang = lang
        self.tld = tld
        self.slow = slow

    def speak(self, text: str) -> bool:
        if not is_speakable(text):
            return True
        from gtts import gTTS
        tmp = str(TEMP_TTS_FILE)
        try:
            for deneme in range(3):
                try:
                    gTTS(text=text, lang=self.lang, tld=self.tld, slow=self.slow).save(tmp)
                    if os.path.exists(tmp) and os.path.getsize(tmp) > 1024:
                        EdgeTTS._play_native(tmp)
                        return True
                    print(f"   ⚠️  Ses boş geldi, tekrar deneniyor ({deneme + 1}/3)")
                except Exception as e:
                    print(f"   ⚠️  gTTS hatası ({deneme + 1}/3): {str(e)[:60]}")
                time.sleep(0.4)
            return False
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass


class SapiTTS:
    """Windows'un kendi ses motoru — tamamen yerel."""

    name = "Windows SAPI (yerel)"

    def __init__(self):
        import pyttsx3
        self.engine = pyttsx3.init()
        for v in self.engine.getProperty("voices"):
            if "tr" in (v.id + v.name).lower():
                self.engine.setProperty("voice", v.id)
                break

    def speak(self, text: str) -> bool:
        try:
            self.engine.say(text)
            self.engine.runAndWait()
            return True
        except Exception as e:
            print(f"⚠️  SAPI hatası: {e}")
            return False


class NullTTS:
    name = "kapalı"

    def speak(self, text: str) -> bool:
        return True


class ChainTTS:
    """İlk motor başarısız olursa (örn. internet yok) yedek motora geçer."""

    def __init__(self, engines: List[Any]):
        self.engines = engines
        self.name = " → ".join(e.name for e in engines)

    def speak(self, text: str) -> bool:
        for engine in self.engines:
            if engine.speak(text):
                return True
        return False


class SpeechStream:
    """Metni parça parça alıp sırayla seslendirir.

    Böylece model yanıtın geri kalanını üretirken Jarvis konuşmaya başlar:
    hem ilk ses çok daha erken gelir hem de konuşma akıcı olur.
    """

    def __init__(self, tts):
        self.tts = tts
        self._q: "queue.Queue[Optional[str]]" = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def say(self, text: str):
        if os.environ.get("JARVIS_DEBUG"):
            print(f"   [tts kuyruğu] {text[:60]!r}")
        # Tek harften kısa ya da sadece simge içeren parçaları atla
        if len(text.strip()) >= 2 and is_speakable(text):
            self._q.put(text)

    def finish(self):
        self._q.put(None)
        self._thread.join()

    def _run(self):
        while True:
            item = self._q.get()
            if item is None:
                break
            self.tts.speak(item)


def build_tts(cfg: Config):
    if cfg.tts_engine == "none":
        return NullTTS()

    engines: List[Any] = []
    if cfg.tts_engine in ("auto", "edge"):
        try:
            engines.append(EdgeTTS(cfg.voice, cfg.voice_rate, cfg.voice_pitch))
        except ImportError:
            if cfg.tts_engine == "edge":
                raise SystemExit("❌ edge-tts kurulu değil: python -m pip install edge-tts")
    if cfg.tts_engine == "gtts":
        engines.clear()
        try:
            engines.append(GoogleTranslateTTS())
        except ImportError:
            raise SystemExit("❌ gTTS kurulu değil: python -m pip install gTTS")
    if cfg.tts_engine in ("auto", "sapi"):
        try:
            engines.append(SapiTTS())
        except ImportError:
            if cfg.tts_engine == "sapi":
                raise SystemExit("❌ pyttsx3 kurulu değil: python -m pip install pyttsx3")
    if not engines:
        return NullTTS()
    return engines[0] if len(engines) == 1 else ChainTTS(engines)


# ----------------------------------------------------------------------------
# MİKROFON + SESSİZLİK ALGILAMA (VAD)
# ----------------------------------------------------------------------------
class MicListener:
    """Sabit süre beklemek yerine: konuşma başlayınca kaydeder, susunca keser.

    Bazı mikrofonlar (ör. Intel Smart Sound dizisi) paylaşımlı modda dijital sessizlik
    verir; bu durumda WASAPI özel modu (`exclusive=True`) kullanılır.
    """

    def __init__(self, samplerate: Optional[int] = None, device: Optional[int] = None,
                 silence_seconds: float = 0.9, max_seconds: int = 15, exclusive: bool = False):
        self.device = device
        self.exclusive = exclusive
        self.samplerate = int(samplerate or 16000)
        self.silence_seconds = silence_seconds
        self.max_seconds = max_seconds
        self.block = max(int(self.samplerate * 0.03), 1)      # 30 ms
        self.extra = None
        if exclusive:
            try:
                self.extra = sd.WasapiSettings(exclusive=True)
            except Exception:
                print("⚠️  WASAPI özel modu desteklenmiyor, paylaşımlı moda dönülüyor.")
                self.exclusive = False
        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._open_stream = None

    # -- akış yönetimi --------------------------------------------------------
    # WASAPI özel modda akışı sık açıp kapatmak cihazı sessizleştirebiliyor;
    # bu yüzden akış oturum boyunca açık tutulur.
    def _new_stream(self):
        return sd.InputStream(samplerate=self.samplerate, channels=1, dtype="float32",
                              blocksize=self.block, device=self.device,
                              extra_settings=self.extra, callback=self._callback)

    def open(self):
        """Mikrofon akışını açık tut (start_voice_loop başında çağrılır)."""
        if self._open_stream is None:
            self._open_stream = self._new_stream()
            self._open_stream.start()

    def close(self):
        if self._open_stream is not None:
            try:
                self._open_stream.stop()
                self._open_stream.close()
            except Exception:
                pass
            self._open_stream = None

    def _active_stream(self):
        """Kullanılabilir akış; kalıcı akış yoksa geçici bir tane açar."""
        if self._open_stream is not None:
            return _SharedStream(self._open_stream)
        return _SharedStream(self._new_stream(), managed=True)

    def drain(self):
        """Tampondaki eski blokları at (yeni dinlemeye temiz başlamak için)."""
        self._q = queue.Queue()

    def _callback(self, indata, _frames, _t, status):  # pragma: no cover
        self._q.put(indata[:, 0].copy())

    def _rms(self, chunk: np.ndarray) -> float:
        return float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)) + 1e-9)

    def calibrate(self, seconds: float = 0.7) -> float:
        print("🎚️  Ortam sesi ölçülüyor, sessiz olun...")
        with self._active_stream():
            time.sleep(seconds)
        levels = []
        while not self._q.empty():
            levels.append(self._rms(self._q.get()))
        ambient = float(np.mean(levels)) if levels else 0.005
        threshold = max(ambient * 3.0, 0.012)
        print(f"   ortam={ambient:.4f}  eşik={threshold:.4f}  "
              f"(cihaz={self.device}, {self.samplerate} Hz{', özel mod' if self.exclusive else ''})")
        if ambient < 1e-6:
            print("   ⚠️  Mikrofon dijital sessizlik veriyor. Klavyedeki mikrofon kapatma tuşunu")
            print("      kontrol edin; ayrıntı için: python mikrofon_test.py")
        return threshold

    def listen_once(self, threshold: float, prompt: str = "🎙️  Dinliyorum...") -> Optional[np.ndarray]:
        """Konuşma algılanana kadar bekler, susunca int16 numpy dizisi döndürür."""
        print(prompt)
        self._q = queue.Queue()
        frames: List[np.ndarray] = []
        block_s = self.block / self.samplerate
        silence_blocks = max(int(self.silence_seconds / block_s), 1)
        max_blocks = max(int(self.max_seconds / block_s), 1)
        started = False
        silent_run = 0
        pre_roll: List[np.ndarray] = []

        deadline = time.time() + self.max_seconds + 5      # ses gelmezse sonsuz bekleme
        with self._active_stream():
            for _ in range(max_blocks):
                if time.time() > deadline:
                    return None
                try:
                    chunk = self._q.get(timeout=1.0)
                except queue.Empty:
                    continue
                level = self._rms(chunk)

                if not started:
                    pre_roll.append(chunk)
                    pre_roll = pre_roll[-6:]              # ~0.2 sn ön kayıt
                    if level > threshold:
                        started = True
                        frames.extend(pre_roll)
                    continue

                frames.append(chunk)
                silent_run = silent_run + 1 if level <= threshold else 0
                if silent_run >= silence_blocks:
                    break

        if not frames:
            return None
        audio = np.concatenate(frames)
        audio = audio[:(len(audio) // self.block) * self.block]

        # Baştaki/sondaki sessizliği kırp; konuşma kenarlarına 0.3 sn pay bırak
        # (sessiz harflerle başlayan/biten kelimeler kesilmesin).
        block_rms = np.sqrt(np.mean(audio.reshape(-1, self.block) ** 2, axis=1))
        loud = np.where(block_rms > threshold * 0.5)[0]
        if len(loud) == 0:
            return None
        pad = int(0.3 * self.samplerate)
        start = max(0, loud[0] * self.block - pad)
        end = min(len(audio), (loud[-1] + 1) * self.block + pad)
        audio = audio[start:end]
        if len(audio) < self.samplerate * 0.3:            # 0.3 sn'den kısa -> gürültü
            return None
        return np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)


class _SharedStream:
    """Zaten açık olan akışı `with` bloğunda kullanmayı sağlar."""

    def __init__(self, stream, managed: bool = False):
        self.stream = stream
        self.managed = managed

    def __enter__(self):
        if self.managed:
            self.stream.start()
        return self.stream

    def __exit__(self, *exc):
        if self.managed:
            self.stream.stop()
            self.stream.close()
        return False


def resample_int16(audio: np.ndarray, sr_in: int, sr_out: int = 16000) -> np.ndarray:
    """Mikrofonun frekansını (ör. 48 kHz) Whisper'ın beklediği 16 kHz'e indirir."""
    if sr_in == sr_out or audio.size == 0:
        return audio
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(int(sr_in), int(sr_out))
    out = resample_poly(audio.astype(np.float32), sr_out // g, sr_in // g)
    return np.clip(out, -32768, 32767).astype(np.int16)


def free_vram_mb() -> Optional[int]:
    """Boş ekran kartı belleği (MB). Bilinemiyorsa None."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=6,
        ).stdout.strip().splitlines()[0]
        total, used = (int(x) for x in out.split(","))
        return total - used
    except Exception:
        return None


def normalize_int16(audio: np.ndarray, target_peak: float = 0.9, max_gain: float = 40.0) -> np.ndarray:
    """Kısık kaydı yükseltir — Whisper kısık sesi çok daha kötü anlıyor."""
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio))) / 32768.0
    if peak < 1e-5:                      # tamamen sessiz
        return audio
    gain = min(target_peak / peak, max_gain)
    return np.clip(audio.astype(np.float32) * gain, -32768, 32767).astype(np.int16)


SILENCE_DB = -75.0                       # bu seviyenin altı "sessiz" kabul edilir
MIC_CACHE_FILE = BASE_DIR / "mic_config.json"


def _db(rms: float) -> float:
    return 20 * math.log10(rms + 1e-12)


def measure_input(device: int, samplerate: int, exclusive: bool = False, seconds: float = 0.4):
    """Cihazı kısa süre açıp seviyeyi ölçer; (rms, hata) döndürür."""
    try:
        extra = sd.WasapiSettings(exclusive=True) if exclusive else None
        block = max(int(samplerate * 0.03), 1)
        with sd.InputStream(device=device, samplerate=samplerate, channels=1, dtype="float32",
                            blocksize=block, extra_settings=extra) as st:
            block = max(int(st.samplerate * 0.03), 1)
            chunks, t0 = [], time.time()
            while time.time() - t0 < seconds:
                data, _ = st.read(block)
                chunks.append(data[:, 0].copy())
        return float(np.sqrt(np.mean(np.concatenate(chunks) ** 2))), ""
    except Exception as e:
        return 0.0, f"{type(e).__name__}: {str(e)[:70]}"


def _remember_mic(device: int, samplerate: int, exclusive: bool) -> None:
    try:
        MIC_CACHE_FILE.write_text(
            json.dumps({"device": device, "samplerate": samplerate, "exclusive": exclusive}),
            encoding="utf-8",
        )
    except Exception:
        pass


def detect_input_device(cfg: Config):
    """Ses veren mikrofonu bulur: (device, samplerate, exclusive). Bulamazsa (None, 16000, False)."""
    if cfg.input_device is not None:
        info = sd.query_devices(cfg.input_device)
        sr = cfg.input_samplerate or int(info["default_samplerate"])
        return cfg.input_device, sr, cfg.input_exclusive

    def describe(idx, sr, excl, rms, etiket):
        print(f"🎙️  Mikrofon ({etiket}): [{idx}] {sd.query_devices(idx)['name'][:40]} — "
              f"{sr} Hz{', özel mod' if excl else ''} (seviye {_db(rms):.1f} dBFS)")
        if _db(rms) < -80:
            print("   ℹ️  Seviye çok düşük. Bazı mikrofonlar (Intel/Nahimic gibi) sessizlikte sesi")
            print("      kısar, siz konuşunca açılır. Tanıma olmazsa: python mikrofon_test.py")

    # 1) Daha önce çalıştığı hatırlanan cihaz — açılabiliyorsa kullan.
    #    (Sessizlikte ses kısan mikrofonları seviyeye bakarak elemek yanlış olur.)
    if MIC_CACHE_FILE.exists():
        try:
            saved = json.loads(MIC_CACHE_FILE.read_text(encoding="utf-8"))
            rms, err = measure_input(saved["device"], saved["samplerate"], saved["exclusive"])
            if not err:
                describe(saved["device"], saved["samplerate"], saved["exclusive"], rms, "hatırlanan")
                return saved["device"], saved["samplerate"], saved["exclusive"]
        except Exception:
            pass

    # 2) Windows'un varsayılan kayıt cihazı açılıyorsa onu kullan (diğer uygulamalarla uyumlu)
    default_in = int(sd.default.device[0]) if sd.default.device[0] is not None else -1
    if default_in >= 0 and sd.query_devices(default_in).get("max_input_channels", 0) > 0:
        sr = int(sd.query_devices(default_in)["default_samplerate"])
        rms, err = measure_input(default_in, sr, False)
        if not err:
            describe(default_in, sr, False, rms, "varsayılan")
            _remember_mic(default_in, sr, False)
            return default_in, sr, False

    candidates = [i for i, d in enumerate(sd.query_devices())
                  if d.get("max_input_channels", 0) > 0
                  and "eşleştiricisi" not in d["name"].lower()]
    if not candidates:
        return None, 16000, False

    print("🔎 Mikrofon taranıyor...")
    best = None

    # 3) Paylaşımlı mod: açılan cihazlar arasından en yüksek seviyeli olanı seç
    for i in candidates:
        info = sd.query_devices(i)
        sr = int(info["default_samplerate"])
        rms, err = measure_input(i, sr, False)
        if err:
            continue
        print(f"   [{i}] {info['name'][:38]:38s} {_db(rms):6.1f} dBFS")
        if best is None or rms > best[3]:
            best = (i, sr, False, rms)
        if _db(rms) > SILENCE_DB:
            _remember_mic(i, sr, False)
            return i, sr, False

    # 4) WASAPI özel mod (paylaşımlı modda gerçekten sessiz kalan mikrofonlar için)
    wasapi = next((h for h, api in enumerate(sd.query_hostapis())
                   if "WASAPI" in api["name"].upper()), None)
    if wasapi is not None:
        for i in candidates:
            info = sd.query_devices(i)
            if info["hostapi"] != wasapi:
                continue
            sr = int(info["default_samplerate"])
            rms, err = measure_input(i, sr, True)
            if err:
                continue
            print(f"   [{i}] {info['name'][:38]:38s} {_db(rms):6.1f} dBFS (özel mod)")
            if best is None or rms > best[3]:
                best = (i, sr, True, rms)
            if _db(rms) > SILENCE_DB:
                _remember_mic(i, sr, True)
                return i, sr, True

    # 5) Şu an sessiz görünse de açılabilen bir cihaz varsa onunla devam et
    if best is not None:
        idx, sr, excl, rms = best
        print("   ℹ️  Şu an sessiz ama açılıyor; konuştuğunuzda açılabilir.")
        if excl:
            print("      (bu cihaz yalnızca WASAPI özel modda veri veriyor)")
        _remember_mic(idx, sr, excl)
        return idx, sr, excl

    return None, 16000, False


# ----------------------------------------------------------------------------
# HIZLI GÖREVLER (GPU'SIZ) + İNTERNET
# ----------------------------------------------------------------------------
ILLER = (
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya",
    "Ardahan", "Artvin", "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik",
    "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
    "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir",
    "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Iğdır", "Isparta", "İstanbul",
    "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale",
    "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa",
    "Mardin", "Mersin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize",
    "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak", "Tekirdağ",
    "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak",
)

WMO_TR = {
    0: "açık", 1: "az bulutlu", 2: "parçalı bulutlu", 3: "kapalı",
    45: "puslu", 48: "kırağılı puslu",
    51: "hafif çisenti", 53: "çisenti", 55: "yoğun çisenti",
    61: "hafif yağmurlu", 63: "yağmurlu", 65: "şiddetli yağmurlu",
    66: "dondurucu yağmurlu", 67: "dondurucu yağmurlu",
    71: "hafif kar yağışlı", 73: "kar yağışlı", 75: "yoğun kar yağışlı", 77: "kar taneli",
    80: "hafif sağanak", 81: "sağanak yağışlı", 82: "şiddetli sağanak",
    85: "kar sağanaklı", 86: "yoğun kar sağanaklı",
    95: "gök gürültülü fırtına", 96: "dolulu fırtına", 99: "şiddetli dolulu fırtına",
}
GUNLER = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
AYLAR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
         "Eylül", "Ekim", "Kasım", "Aralık")


class ToolBox:
    """Saat, tarih, hava durumu, hafıza sorgusu: model/GPU kullanılmadan anında yanıtlar."""

    def __init__(self, memory: "MemoryEngine", cfg: Config):
        self.memory = memory
        self.cfg = cfg

    def fast_answer(self, text: str) -> Optional[str]:
        t = normalize_tr(text)
        if not t:
            return None
        if re.search(r"\b(saat|saati|saat kac)\b", t):
            return self._clock()
        if re.search(r"\b(tarih|bugun gunlerden|hangi gun|gunlerden ne)\b", t):
            return self._date()
        if re.search(r"\b(hafizan|hafizanda|neler biliyorsun|hatirladiklarin|hafiza)\b", t):
            return self._memory_report()
        if re.search(r"\bhava\b", t) or "hava durumu" in t:
            return self._weather(text)
        return None

    # -- saat / tarih ---------------------------------------------------------
    @staticmethod
    def _clock() -> str:
        now = datetime.now()
        return f"Efendim, saat şu an {now.hour:02d}:{now.minute:02d}."

    @staticmethod
    def _date() -> str:
        now = datetime.now()
        return (f"Efendim, bugün {now.day} {AYLAR[now.month - 1]} {now.year}, "
                f"{GUNLER[now.weekday()]}.")

    def _memory_report(self) -> str:
        facts = self.memory.all_facts()
        cache = self.memory.cache_summary()
        parca = [f"Efendim, sizinle ilgili {len(facts)} kayıt tutuyorum." if facts else
                 "Efendim, henüz sizinle ilgili özel bir kaydım yok."]
        if facts:
            parca.append("Kayıtlar: " + "; ".join(facts[:4]) + ".")
        if cache:
            parca.append(f"Ayrıca {len(cache)} güncel bilgi önbellekte duruyor.")
        return " ".join(parca)

    # -- hava durumu (Open-Meteo, API anahtarı gerekmez) ----------------------
    def _city(self, text: str) -> str:
        t = normalize_tr(text)
        for il in ILLER:
            if normalize_tr(il) in t:
                return il
        return self.cfg.default_city

    def _weather(self, text: str) -> Optional[str]:
        city = self._city(text)
        cache_key = f"hava:{normalize_tr(city)}"
        cached = self.memory.cache_get(cache_key)
        if cached:
            return cached
        try:
            geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                               params={"name": city, "count": 1, "language": "tr", "format": "json"},
                               timeout=8).json()
            if not geo.get("results"):
                return f"Efendim, {city} konumunu bulamadım."
            loc = geo["results"][0]
            data = requests.get("https://api.open-meteo.com/v1/forecast",
                                params={"latitude": loc["latitude"], "longitude": loc["longitude"],
                                        "current": "temperature_2m,apparent_temperature,weather_code,"
                                                   "wind_speed_10m,relative_humidity_2m",
                                        "timezone": "auto"},
                                timeout=8).json().get("current", {})
            durum = WMO_TR.get(int(data.get("weather_code", -1)), "bilinmiyor")
            cevap = (f"Efendim, {loc['name']} için hava şu an {durum}, "
                     f"{round(data.get('temperature_2m', 0))} derece. "
                     f"Hissedilen {round(data.get('apparent_temperature', 0))} derece, "
                     f"nem yüzde {round(data.get('relative_humidity_2m', 0))}, "
                     f"rüzgâr {round(data.get('wind_speed_10m', 0))} kilometre saat.")
            self.memory.cache_set(cache_key, cevap, 900, "hava")      # 15 dakika
            print(f"   🌐 Hava verisi: open-meteo.com ({loc['name']}) — önbelleğe yazıldı")
            return cevap
        except Exception as e:
            print(f"   ⚠️  Hava durumu alınamadı: {type(e).__name__}")
            return None


class WebSearch:
    """ddgs ile internet araması; sonuç özeti hafızada saklanır (tekrar sorulursa anında gelir)."""

    ANAHTAR_KELIMELER = (
        "kim", "kimdir", "nedir", "ne zaman", "kac", "hangi yil", "haber", "son dakika",
        "guncel", "fiyat", "kac lira", "ara", "internet", "google", "arastir", "skor",
        "mac sonucu", "hava durumu", "bugun", "yarin", "puan", "siralama", "ozet",
    )

    def __init__(self, memory: "MemoryEngine", cfg: Config):
        self.memory = memory
        self.cfg = cfg

    def needs_internet(self, text: str) -> bool:
        if not self.cfg.internet:
            return False
        t = normalize_tr(text)
        return any(k in t for k in self.ANAHTAR_KELIMELER)

    def search(self, query: str, max_results: int = 3) -> str:
        """İnternet araması. Sonuçlar önbelleğe yazılır; aynı sorgu tekrar sorulursa anında gelir."""
        key = f"arama:{normalize_tr(query)}"
        cached = self.memory.cache_get(key)
        if cached:
            print(f"   💾 Hafızadan (önbellek): {key[6:]}")
            return cached
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            satirlar = []
            with DDGS() as ddgs:
                for i, r in enumerate(ddgs.text(query, region="tr-tr", max_results=max_results), 1):
                    baslik = (r.get("title") or "").strip()
                    ozet = (r.get("body") or "").strip()
                    if baslik or ozet:
                        satirlar.append(f"{i}. {baslik} — {ozet[:200]}")
            if not satirlar:
                return ""
            sonuc = "\n".join(satirlar)
            self.memory.cache_set(key, sonuc, 86400, "internet")     # 1 gün
            print(f"   🌐 {len(satirlar)} sonuç bulundu ve önbelleğe yazıldı")
            return sonuc
        except Exception as e:
            print(f"   ⚠️  Arama başarısız: {type(e).__name__}: {str(e)[:60]}")
            return ""


# ----------------------------------------------------------------------------
# BEYİN
# ----------------------------------------------------------------------------
SYSTEM_PROMPT = """Sen Jarvis adında, Iron Man'in yapay zekasına benzer, Türkçe konuşan, beyefendi, akıllı ve zamanla kullanıcısını tanıyan kişisel bir asistansın.

[KULLANICI HAKKINDA BİLİNEN HAFIZA]
{profile}

[GÖREVLERİN]
1. Kullanıcıya doğrudan Jarvis olarak, saygılı ("Efendim") ve karizmatik bir dille yanıt ver.
2. Konuşma diline uygun, akıcı ve KISA yanıt ver: en fazla 2 cümle, toplam 25 kelimeyi geçme. Sesli okunacağı için madde işareti, emoji ve biçimlendirme KULLANMA.
3. Etiketi SADECE kullanıcı kendisi, adı, donanımı, hobileri veya tercihleri hakkında yukarıdaki hafıza listesinde BULUNMAYAN kalıcı bir bilgi verdiyse kullan: yanıtın en sonuna `[ÖĞRENİLEN_BİLGİ: ...]` yaz.
4. Hafızada zaten yazan bir bilgiyi (örneğin kullanıcının adı) veya o anlık durumları (hava, saat, ruh hali) ASLA etiketleme. Yeni bilgi yoksa `[ÖĞRENİLEN_BİLGİ]` etiketini HİÇ EKLEME.
5. Bilmediğin bir şey sorulursa uydurma; kısa ve dürüst cevap ver.
6. Güncel bilgi gerekiyorsa (haber, skor, fiyat, hava, "bugün", "son" vb.) ve sana [İNTERNETTEN ALINAN GÜNCEL BİLGİLER] verilmemişse, yanıtın SADECE şu biçimde olsun: [ARA: fenerbahçe son maç sonucu] — yani köşeli parantezin içine konunun GERÇEK arama sorgusunu yaz. İnternet sonucu verilmişse onu kullanıp doğrudan cevap ver.
7. [İNTERNETTEN ALINAN GÜNCEL BİLGİLER] verilmişse ASLA tekrar [ARA: ...] yazma; gelen bilgiyi özetle."""

# Türkçe karakterleri sadeleştirme ("cikis" == "çıkış", "Ahmet'in" vb.)
TR_FOLD = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def normalize_tr(text: str) -> str:
    return text.translate(TR_FOLD).lower().strip()


# Cümle sonu: akış halinde gelen yanıtı cümle cümle seslendirmek için
SENTENCE_END = re.compile(r"[.!?…:](?=\s|$)")

FACT_PATTERN = re.compile(r"\[ÖĞRENİLEN_BİLGİ:\s*(.*?)\]", re.DOTALL)
ARAMA_PATTERN = re.compile(r"\[ARA:\s*(.*?)\]", re.DOTALL)

# Modele uydurma/çıkarım yapan bilgileri hafızaya yazmama için
SPEKULASYON_KELIMELERI = ("belki", "muhtemelen", "gibi gorunuyor", "bilinmiyor", "bilinmeyen", "olabilir",
                         "sanirim", "tahmin", "dikkatli ol", "emin degilim", "galiba", "saniyorum")
THINK_PATTERN = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)
# Sesli okumada bozuk çıkan emoji / biçimlendirme karakterleri
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"          # emoji blokları
    "\U00002190-\U000021FF"          # oklar
    "\U00002600-\U000027BF"          # semboller/dinkaatlar
    "\U00002B00-\U00002BFF"
    "\U0000FE0F\U0000200D\U000024C2"
    "]+"
)


def clean_for_speech(text: str) -> str:
    text = EMOJI_PATTERN.sub("", text)
    text = re.sub(r"[#*_`>]+|\[(.*?)\]\(.*?\)", "", text)   # markdown ve linkler
    # Sadece seslendirilebilir karakterler kalsın (emoji/simge kalırsa TTS hata veriyor)
    text = "".join(ch for ch in text
                    if ch.isalnum() or ch.isspace() or ch in ".,!?;:%-'’\"()")
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def is_speakable(text: str) -> bool:
    """İçinde okunacak harf/rakam var mı? ("🚀" gibi parçaları atlar)"""
    return any(ch.isalnum() for ch in text)


class WhisperBrain:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.memory = MemoryEngine(cfg.db_path)
        self.tools = ToolBox(self.memory, cfg)          # GPU'suz hızlı görevler
        self.web = WebSearch(self.memory, cfg)          # internet araması + önbellek
        self.voice = build_tts(cfg)
        if cfg.backend == "gemini":
            self.llm = GeminiLLM(cfg.gemini_api_key)
        else:
            self.llm = detect_backend(cfg, required=False)      # sunucu kapalıysa hata verme
        if self.llm is None:
            print("⚠️  Yerel model sunucusu şu an kapalı.")
            print("   • Basit görevler (saat, tarih, hava durumu, hafıza, önbellek) çalışmaya devam eder.")
            print("   • Model gerektiren bir soru gelirse otomatik başlatmayı deneyeceğim.")
            print("   • Elle başlatmak için: lms server start")
        self.stt = None                       # sadece sesli modda kurulur
        self.listener: Optional[MicListener] = None
        self.threshold = 0.02
        self._turn_start = 0.0
        self._exit_set = {normalize_tr(w) for w in cfg.exit_words}

    # -- LLM -----------------------------------------------------------------
    def system_prompt(self, internet_context: str = "") -> str:
        system = SYSTEM_PROMPT.format(profile=self.memory.get_user_profile())
        history = self.memory.recent_history(4)
        if history:
            history_txt = "\n".join(f"Siz: {u}\nJarvis: {a}" for u, a in history)
            system += f"\n\n[SON KONUŞMA ÖZETİ]\n{history_txt}"
        if internet_context:
            system += ("\n\n[İNTERNETTEN ALINAN GÜNCEL BİLGİLER]\n" + internet_context[:2500] +
                       "\n\nBu bilgileri kullanarak kullanıcıya doğrudan ve kısa cevap ver; kaynak adı okuma.")
        return system

    def generate(self, command: str, internet_context: str = "") -> str:
        return self.llm.chat(self.system_prompt(internet_context), command)

    def _stream_turn(self, command: str, internet_context: str = ""):
        """Yanıtı akış halinde alıp cümle bittiğinde hemen okur.

        Böylece model kalanı üretirken Jarvis konuşmaya başlar: ilk ses belirgin
        şekilde erken gelir ve konuşma kesintisiz/akıcı olur.
        Returns: (tam_metin, seslendirilen_metin)
        """
        speech = SpeechStream(self.voice)
        speech.start()
        buffer, full, spoken_parts = "", "", []
        tag_started, first_chunk = False, True
        try:
            for delta in self.llm.chat_stream(self.system_prompt(internet_context), command):
                full += delta
                if tag_started:                 # [ÖĞRENİLEN_BİLGİ...] başladı: okumaya katma
                    continue
                if "[" in delta:
                    tag_started = True
                    delta = delta.split("[", 1)[0]
                if not delta:
                    continue
                buffer += delta
                print(delta, end="", flush=True)
                while True:
                    m = SENTENCE_END.search(buffer)
                    if not m or m.end() < 12:   # çok kısa parçaları biriktir
                        break
                    chunk, buffer = buffer[:m.end()], buffer[m.end():]
                    spoken = clean_for_speech(chunk)
                    if spoken:
                        if first_chunk:
                            first_chunk = False
                            print(f"\n   ⏱️  İlk ses {time.time() - self._turn_start:.1f} sn'de başlıyor",
                                  flush=True)
                        spoken_parts.append(spoken)
                        speech.say(spoken)
            tail = clean_for_speech(buffer)
            if tail:
                spoken_parts.append(tail)
                speech.say(tail)
        except Exception:
            speech.finish()
            raise
        print()
        speech.finish()                          # konuşma bitene kadar bekle
        return full, " ".join(spoken_parts).strip()

    def process_command(self, command: str) -> Dict[str, Any]:
        command = (command or "").strip()
        if not command:
            return {"status": "empty", "response": ""}

        self._turn_start = time.time()
        t0 = self._turn_start

        # 1) BASİT GÖREV: saat, tarih, hava durumu, hafıza sorgusu -> model/GPU kullanılmaz
        hizli = self.tools.fast_answer(command)
        if hizli:
            print(f"⚡ Hızlı yanıt (model/GPU kullanılmadı)")
            print(f"🔊 Jarvis ({time.time() - t0:.2f} sn): {hizli}")
            self.memory.save_interaction(command, hizli)
            self.voice.speak(hizli)
            return {"status": "success", "response": hizli, "fast": True}

        # 2) GEREKİYORSA İNTERNET: sonuç önbellekte varsa anında, yoksa arayıp hafızaya yazar
        internet_context = ""
        if self.web.needs_internet(command):
            print("🌐 İnternetten bilgi alınıyor...")
            internet_context = self.web.search(command)

        # 3) MODEL YOKSA: internet sonucu varsa ondan cevap ver, yoksa dürüstçe söyle
        if self.llm is None and not self._ensure_llm():
            cevap = (self._ozet_cevap(internet_context) if internet_context else
                     "Efendim, dil modeli şu an kapalı. Saat, tarih, hava durumu ve hafıza "
                     "sorularında yardımcı olabilirim.")
            print(f"🔊 Jarvis ({time.time() - t0:.2f} sn): {cevap}")
            self.memory.save_interaction(command, cevap)
            self.voice.speak(cevap)
            return {"status": "success", "response": cevap, "offline": True}

        print("🧠 Yanıt hazırlanıyor...")
        speech_text = None
        try:
            if self.cfg.tts_sentence_stream:
                raw_response, speech_text = self._stream_turn(command, internet_context)
            else:
                raw_response = self.generate(command, internet_context)
        except Exception as e:
            print(f"❌ Model hatası: {e}")
            self.voice.speak("Sunucuya ulaşamadım efendim.")
            return {"status": "error", "response": str(e)}

        # 3) Model kendi [ARA: ...] etiketiyle internet istediyse ikinci tur
        arama = ARAMA_PATTERN.search(raw_response)
        if arama and self.cfg.internet and not internet_context:
            sorgu = arama.group(1).strip()
            # Model bazen şablonu kopyalıyor ("arama sorgusu"); o durumda kullanıcının cümlesini ara
            if len(sorgu) < 6 or sorgu.lower() in ("arama sorgusu", "sorgu", "query", "arama"):
                sorgu = command
            print(f"🌐 Model internet istedi: {sorgu}")
            self.voice.speak("Efendim, bunu internette araştırıyorum.")
            internet_context = self.web.search(sorgu)
            if internet_context:
                try:
                    raw_response, speech_text = self._stream_turn(command, internet_context)
                except Exception as e:
                    print(f"❌ Model hatası: {e}")
                if not (speech_text or "").strip():        # model yine etiket yazdıysa sonuçtan cevap ver
                    speech_text = self._ozet_cevap(internet_context)
                    print(f"🔊 Jarvis: {speech_text}")
                    self.voice.speak(speech_text)
                    self.memory.save_interaction(command, speech_text)
                    return {"status": "success", "response": speech_text, "internet": True}

        raw_response = THINK_PATTERN.sub("", raw_response).strip()

        fact = None
        match = FACT_PATTERN.search(raw_response)
        if match and match.group(1).strip():
            candidate = match.group(1).strip()
            if not self._fact_guvenilir(candidate, command):
                print(f"🧠 [Bilgi doğrulanamadı, hafızaya yazılmadı]: {candidate}")
            elif self.memory.save_fact(candidate):
                fact = candidate
                print(f"🧠 [Hafızaya kaydedildi]: {fact}")
            else:
                print(f"🧠 [Hafızada zaten var, kaydedilmedi]: {candidate}")

        # Model etiket üretmediyse ama kullanıcı kendisi hakkında bilgi verdiyse: ayrıca çıkar
        if fact is None and self.llm is not None and self._kisisel_ifade_var(command):
            for bilgi in self._bilgi_cikar(command):
                if self._fact_guvenilir(bilgi, command) and self.memory.save_fact(bilgi):
                    fact = bilgi
                    print(f"🧠 [Hafızaya kaydedildi]: {bilgi}")

        if speech_text is None:                  # akış kullanılmadıysa tek seferde oku
            speech_text = clean_for_speech(ARAMA_PATTERN.sub("", FACT_PATTERN.sub("", raw_response)))
            self.voice.speak(speech_text)

        self.memory.save_interaction(command, speech_text)
        print(f"🔊 Jarvis ({time.time() - t0:.1f} sn): {speech_text}")
        return {"status": "success", "response": speech_text, "learned": fact}

    def _ensure_llm(self) -> bool:
        """Model sunucusu kapalıysa başlatmayı dener (hızlı görevler için gerekmez)."""
        if self.llm is not None:
            return True
        print("⏳ Yerel model sunucusu başlatılıyor...")
        try_start_lmstudio_server()
        try:
            self.llm = detect_backend(self.cfg, required=False)
        except SystemExit:
            self.llm = None
        if self.llm is not None and ensure_lmstudio_model(self.llm.model, self.cfg.llm_context):
            try:
                self.llm = detect_backend(self.cfg, required=False)   # yeni yükleme ile tazele
            except SystemExit:
                pass
        if self.llm is not None:
            print("✅ Model hazır.")
            return True
        return False

    @staticmethod
    def _ozet_cevap(context: str) -> str:
        """Model yokken internet sonucundan kısa bir cevap üretir."""
        ilk = context.splitlines()[0] if context else ""
        ilk = re.sub(r"^\d+\.\s*", "", ilk)
        baslik, _, ozet = ilk.partition("—")
        metin = (ozet or baslik).strip()[:220]
        return f"Efendim, bulduğum bilgi şu: {metin}"

    # Kullanıcının kendisi hakkında bilgi verdiğini gösteren ifadeler
    KISISEL_IFADELER = (
        "adim", "ismim", "benim adim", "soyadim", "kedimin", "kopegimin", "evcil", "esimin",
        "kardesim", "oglum", "kizim", "yasiyorum", "oturuyorum", "calisiyorum", "okuyorum",
        "seviyorum", "severim", "hobim", "hobilerim", "tercih ediyorum", "bundan sonra bana",
        "kullaniyorum", "ekran karti", "islemci", "bilgisayarim", "telefonum", "meslegim",
        "dogum gunum", "yasim", "kac yasindayim", "en sevdigim", "hosuma gidiyor",
    )

    def _kisisel_ifade_var(self, command: str) -> bool:
        t = normalize_tr(command)
        return any(k in t for k in self.KISISEL_IFADELER)

    def _bilgi_cikar(self, command: str) -> List[str]:
        """Modele küçük bir 'bilgi çıkarma' görevi verir (etiket üretmese bile hafıza çalışır)."""
        sistem = ("Kullanıcının cümlesinden kalıcı, kişisel bilgileri çıkar "
                  "(adı, eşyaları, hobileri, tercihleri, cihazları, yaşadığı yer). "
                  'Yanıtı SADECE JSON olarak ver: {"bilgiler": ["kısa bilgi", "..."]}. '
                  'Kişisel bilgi yoksa {"bilgiler": []} döndür. Uydurma, sadece cümlede geçeni yaz.')
        try:
            yanit = self.llm.chat(sistem, command)
        except Exception:
            return []
        adaylar = [s for s in re.findall(r'"([^"]{3,90})"', yanit) if s.lower() != "bilgiler"]
        return [a.strip() for a in adaylar if a.strip()]

    def _fact_guvenilir(self, fact: str, command: str) -> bool:
        """Sadece kullanıcının kendi cümlesinde söylediği bilgiler hafızaya yazılır."""
        nf = normalize_tr(fact)
        if any(s in nf for s in SPEKULASYON_KELIMELERI):
            return False
        tokens = set(re.findall(r"\w+", nf)) - STOPWORDS
        komut = set(re.findall(r"\w+", normalize_tr(command))) - STOPWORDS
        if not tokens:
            return False
        return len(tokens & komut) / len(tokens) >= 0.5        # bilginin yarısı kullanıcının cümlesinden gelmeli

    def _update_stt_prompt(self) -> None:
        """Whisper'a özel isimleri (kullanıcı bilgileri, son komut) ipucu olarak verir."""
        if not hasattr(self.stt, "initial_prompt"):
            return
        parcalar = [self.cfg.whisper_prompt or ""]
        for fact in self.memory.all_facts()[:4]:
            parcalar.append(fact.replace("-", " ").replace(":", " "))
        self.stt.initial_prompt = (" ".join(parcalar).strip() or None)[:300]

    # -- DÖNGÜLER ------------------------------------------------------------
    def _handle(self, text: str) -> bool:
        """False dönerse çık."""
        if normalize_tr(text).rstrip(".!?") in self._exit_set:
            print("👋 Jarvis kapatılıyor...")
            self.voice.speak("İyi günler dilerim efendim.")
            return False
        if text.strip():
            self.process_command(text)
        return True

    def text_loop(self):
        print("\n==========================================")
        print("⌨️  Jarvis metin modunda (çıkmak için 'çıkış')")
        print("==========================================\n")
        print(f"📋 [Kullanıcı Hafızası]:\n{self.memory.get_user_profile()}\n")
        while True:
            try:
                text = input("🗣️  Siz: ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not self._handle(text):
                break

    def start_voice_loop(self):
        if self.stt is None:
            self.stt = build_stt(self.cfg)
        if self.listener is None:
            device, samplerate, exclusive = detect_input_device(self.cfg)
            if device is None:
                print("\n❌ Ses veren bir mikrofon bulunamadı.")
                print("   Kontrol listesi:")
                print("   • Klavyedeki mikrofon kapatma tuşu (LED'i yanıyor olabilir)")
                print("   • Ayarlar → Gizlilik ve güvenlik → Mikrofon: izinler açık olmalı")
                print("   • mmsys.cpl → Kayıt → mikrofon → Düzeyler: %100 ve sessiz değil")
                print("   • Ayrıntılı test: python mikrofon_test.py")
                print("   • Mikrofon düzelene kadar yazı modu: python jarvis_local.py --text")
                raise SystemExit(1)
            self.listener = MicListener(samplerate=samplerate, device=device, exclusive=exclusive,
                                        silence_seconds=self.cfg.silence_seconds,
                                        max_seconds=self.cfg.max_record_seconds)

        dev_idx = self.listener.device if self.listener.device is not None else sd.default.device[0]
        self.listener.device = int(dev_idx)
        mic_info = sd.query_devices(int(dev_idx))
        print("\n==========================================")
        print("⚡ Jarvis Sesli Asistan Sistemleri Aktif!")
        print(f"   LLM: {self.llm.name} | STT: {self.stt.name} | TTS: {self.voice.name}")
        print(f"   Mikrofon: [{self.listener.device}] {mic_info['name'][:45]} — "
              f"{self.listener.samplerate} Hz{', özel mod' if self.listener.exclusive else ''}")
        print("==========================================\n")
        print(f"📋 [Mevcut Kullanıcı Hafızası]:\n{self.memory.get_user_profile()}\n")

        self.listener.open()          # mikrofonu oturum boyunca açık tut
        try:
            self.threshold = self.listener.calibrate()
        except Exception as e:
            self.listener.close()
            print(f"❌ Mikrofon açılamadı: {e}")
            raise SystemExit(1)
        self.voice.speak("Sistemler ve kişisel hafıza katmanı aktif efendim, sizi dinliyorum.")

        try:
            while True:
                try:
                    self.listener.drain()
                    audio = self.listener.listen_once(self.threshold)
                except KeyboardInterrupt:
                    print("\n👋 Jarvis kapatılıyor...")
                    self.voice.speak("İyi günler dilerim efendim.")
                    break
                if audio is None:
                    continue

                print("⏳ Ses işleniyor...")
                try:
                    self._update_stt_prompt()
                    # Mikrofon 48 kHz gibi farklı frekansta çalışıyorsa 16 kHz'e indir
                    text = self.stt.transcribe(resample_int16(audio, self.listener.samplerate), 16000)
                except Exception as e:
                    print(f"⚠️  Konuşma tanıma hatası: {e}")
                    continue
                if not text.strip():
                    print("⚠️  Ses algılanamadı.")
                    continue
                print(f"🗣️  Siz: {text}")
                if not self._handle(text):
                    break
        finally:
            self.listener.close()


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> Config:
    cfg = Config()
    p = argparse.ArgumentParser(description="Jarvis — yerel yapay zeka ile Türkçe sesli asistan")
    p.add_argument("--backend", default=cfg.backend,
                   choices=["auto", "lmstudio", "ollama", "llamacpp", "gemini"])
    p.add_argument("--base-url", dest="base_url", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--gemini-api-key", dest="gemini_api_key", default="")
    p.add_argument("--voice", default=cfg.voice,
                   help="edge-tts sesi (de-DE-FlorianMultilingualNeural, tr-TR-EmelNeural, "
                        "tr-TR-AhmetNeural, en-US-BrianMultilingualNeural, en-US-AndrewMultilingualNeural ...)")
    p.add_argument("--rate", dest="voice_rate", default=cfg.voice_rate, help="konuşma hızı, ör. +20%%")
    p.add_argument("--pitch", dest="voice_pitch", default=cfg.voice_pitch, help="ton, ör. -5Hz")
    p.add_argument("--no-stream", dest="tts_sentence_stream", action="store_false",
                   help="Akışlı (cümle cümle) konuşmayı kapat, yanıt bitince tek seferde oku")
    p.add_argument("--tts", dest="tts_engine", default=cfg.tts_engine,
                   choices=["auto", "edge", "gtts", "sapi", "none"],
                   help="edge=doğal/ayarlanabilir, gtts=yerli Türkçe Google sesi, sapi=Windows")
    p.add_argument("--stt", dest="stt_engine", default=cfg.stt_engine,
                   choices=["auto", "whisper", "vosk", "google"])
    p.add_argument("--whisper-model", dest="whisper_model", default=cfg.whisper_model)
    p.add_argument("--whisper-device", dest="whisper_device", default=cfg.whisper_device,
                   choices=["auto", "cuda", "cpu"],
                   help="Whisper nerede çalışsın (varsayılan cpu: GPU'yu LLM'e bırakır)")
    p.add_argument("--input-device", dest="input_device", type=int, default=None,
                   help="Kayıt cihazı numarası (python mikrofon_test.py ile bulunur)")
    p.add_argument("--exclusive", dest="input_exclusive", action="store_true",
                   help="Mikrofonu WASAPI özel modda aç (paylaşımlı modda sessiz kalan diziler için)")
    p.add_argument("--text", action="store_true", help="Klavyeden yazı ile sohbet (mikrofon kullanılmaz)")
    p.add_argument("--say", default=None, help="Tek komut çalıştır ve çık")
    p.add_argument("--list-llms", action="store_true", help="Ayakta olan yerel sunucuları/model listesini göster")
    p.add_argument("--start-server", dest="auto_start_server", action="store_true",
                   help="Sunucu kapalıysa LM Studio sunucusunu otomatik başlat")
    p.add_argument("--no-internet", dest="internet", action="store_false",
                   help="İnternet aramasını kapat (sadece yerel model + hafıza)")
    p.add_argument("--city", dest="default_city", default=cfg.default_city,
                   help="Hava durumu için varsayılan şehir")
    p.add_argument("--max-tokens", type=int, default=cfg.max_tokens)
    args = p.parse_args(argv)

    cfg.backend = args.backend
    cfg.base_url = args.base_url
    cfg.model = args.model
    cfg.gemini_api_key = args.gemini_api_key
    cfg.voice = args.voice
    cfg.voice_rate = args.voice_rate
    cfg.voice_pitch = args.voice_pitch
    cfg.tts_sentence_stream = args.tts_sentence_stream
    cfg.tts_engine = args.tts_engine
    cfg.stt_engine = args.stt_engine
    cfg.whisper_model = args.whisper_model
    cfg.whisper_device = args.whisper_device
    cfg.input_device = args.input_device
    cfg.input_exclusive = args.input_exclusive
    cfg.max_tokens = args.max_tokens
    cfg.auto_start_server = args.auto_start_server
    cfg.internet = args.internet
    cfg.default_city = args.default_city

    # Qwen3 gibi "düşünen" modelleri hızlı yanıt için sessizleştir
    cfg.extra_body = _default_extra_body(args.model or "")

    cfg._mode_text = args.text          # type: ignore[attr-defined]
    cfg._say = args.say                 # type: ignore[attr-defined]
    cfg._list = args.list_llms          # type: ignore[attr-defined]
    return cfg


def list_available(cfg: Config):
    print("Yerel LLM sunucuları taranıyor...\n")
    found = False
    for key, url, label in LOCAL_BACKENDS:
        try:
            models = OpenAICompatLLM.list_models(url, cfg.api_key, timeout=2.0)
            found = True
            print(f"✅ {label} — {url}")
            for m in models:
                print(f"     - {m}{'' if _is_chat_model(m) else '   (sohbet modeli değil)'}")
        except Exception as e:
            print(f"❌ {label} — {url}  ({type(e).__name__})")
    if not found:
        print("\n" + SERVER_HELP)


def main(argv: Optional[List[str]] = None):
    cfg = parse_args(argv)

    if getattr(cfg, "_list", False):
        list_available(cfg)
        return

    brain = WhisperBrain(cfg)

    if getattr(cfg, "_say", None):
        brain.process_command(cfg._say)
        return
    if getattr(cfg, "_mode_text", False):
        brain.text_loop()
        return
    brain.start_voice_loop()


if __name__ == "__main__":
    main()
