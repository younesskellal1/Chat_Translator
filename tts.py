"""Text-to-Speech module with multiple backend support."""

import io
import tempfile
import threading
import asyncio

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import edge_tts
except Exception:
    edge_tts = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None

_tts_lock = threading.Lock()

VOICE_MAP = {
    "en-US": "en-US-JennyNeural",
    "en-GB": "en-GB-LibbyNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "es-ES": "es-ES-ElviraNeural",
    "de-DE": "de-DE-KatjaNeural",
    "it-IT": "it-IT-ElsaNeural",
    "pt-PT": "pt-PT-FernandaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "ar-SA": "ar-SA-HamedNeural",
    "ar-EG": "ar-EG-SalmaNeural",
    "ar-AE": "ar-AE-FatimaNeural",
    "ru-RU": "ru-RU-DariyaNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "ko-KR": "ko-KR-SunHiNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "tr-TR": "tr-TR-EmelNeural",
    "nl-NL": "nl-NL-ColetteNeural",
    "sv-SE": "sv-SE-SofieNeural",
    "nb-NO": "nb-NO-IselinNeural",
    "da-DK": "da-DK-ChristelNeural",
    "fi-FI": "fi-FI-NooraNeural",
    "el-GR": "el-GR-AthinaNeural",
    "pl-PL": "pl-PL-AgnieszkaNeural",
    "cs-CZ": "cs-CZ-VlastaNeural",
    "uk-UA": "uk-UA-OstapNeural",
    "ro-RO": "ro-RO-AlinaNeural",
}


def _pick_tts_voice(engine, lang_hint: str | None):
    """Pick appropriate voice for language from available voices."""
    if not lang_hint:
        return None
    try:
        voices = engine.getProperty("voices") or []
        candidates = [lang_hint]
        if "-" in lang_hint:
            candidates.append(lang_hint.split("-")[0])
        for cand in candidates:
            for v in voices:
                langs = []
                try:
                    if hasattr(v, "languages") and v.languages:
                        langs = [
                            (x.decode("utf-8", errors="ignore") if isinstance(x, (bytes, bytearray)) else str(x))
                            for x in v.languages
                        ]
                except Exception:
                    langs = []
                name = getattr(v, "name", "") or ""
                id_ = getattr(v, "id", "") or ""
                bucket = ",".join(langs + [name, id_]).lower()
                if cand.lower().replace("_", "-") in bucket or cand.lower() in bucket:
                    return v.id
        return None
    except Exception:
        return None


async def _synthesize_edge_tts_async(text: str, lang: str) -> bytes:
    """Synthesize speech using edge-tts (online neural voices) - async version."""
    if edge_tts is None:
        raise RuntimeError("edge-tts not available")
    voice = VOICE_MAP.get(lang) or VOICE_MAP.get(lang.split('-')[0] if '-' in lang else lang) or VOICE_MAP['en-US']
    communicate = edge_tts.Communicate(text, voice)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def _synthesize_edge_tts(text: str, lang: str) -> bytes:
    """Synthesize speech using edge-tts (online neural voices) - sync wrapper."""
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, can't use asyncio.run - skip edge-tts
            raise RuntimeError("Event loop already running")
    except RuntimeError:
        pass
    
    try:
        return asyncio.run(_synthesize_edge_tts_async(text, lang))
    except Exception as e:
        raise RuntimeError(f"edge-tts failed: {str(e)}")


def synthesize_tts(text: str, lang: str) -> tuple[bytes, str]:
    """Synthesize text-to-speech using available backends.
    
    Returns tuple of (audio_bytes, mime_type).
    Tries gTTS (Google), then edge-tts (neural), then pyttsx3 (local).
    """
    # Try Google TTS (gTTS) first if available (MP3)
    if gTTS is not None:
        try:
            def _map_to_gtts(l: str) -> str:
                m = {
                    "en-US": "en", "en-GB": "en", "fr-FR": "fr", "es-ES": "es", "de-DE": "de",
                    "it-IT": "it", "pt-PT": "pt", "pt-BR": "pt", "ar-SA": "ar", "ru-RU": "ru",
                    "ja-JP": "ja", "ko-KR": "ko", "zh-CN": "zh-CN", "hi-IN": "hi", "tr-TR": "tr",
                    "nl-NL": "nl", "sv-SE": "sv", "nb-NO": "no", "da-DK": "da", "fi-FI": "fi",
                    "el-GR": "el", "pl-PL": "pl", "cs-CZ": "cs", "uk-UA": "uk", "ro-RO": "ro",
                }
                l = (l or "en").strip()
                return m.get(l, l.split('-')[0] if '-' in l else l)

            lang_code = _map_to_gtts(lang)
            mp3_buf = io.BytesIO()
            gTTS(text=text, lang=lang_code).write_to_fp(mp3_buf)
            mp3_buf.seek(0)
            return mp3_buf.read(), "audio/mpeg"
        except Exception:
            pass

    # Try neural TTS (edge-tts)
    if edge_tts is not None:
        try:
            audio_bytes = _synthesize_edge_tts(text, lang)
            return audio_bytes, "audio/mpeg"
        except Exception:
            pass

    # Fallback to local pyttsx3 WAV
    if pyttsx3 is None:
        raise RuntimeError("No TTS engine available")

    with _tts_lock:
        try:
            engine = pyttsx3.init()
            voice_id = _pick_tts_voice(engine, lang)
            if voice_id:
                try:
                    engine.setProperty("voice", voice_id)
                except Exception:
                    pass
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                engine.save_to_file(text, tmp.name)
                engine.runAndWait()
                tmp.flush()
                tmp.seek(0)
                audio_bytes = tmp.read()
                return audio_bytes, "audio/wav"
        except Exception as e:
            raise RuntimeError(f"TTS synthesis failed: {str(e)}")
