"""Translation module supporting NLLB-200, M2M-100, and Marian models."""

from transformers import MarianMTModel, MarianTokenizer, AutoTokenizer, AutoModelForSeq2SeqLM, M2M100Tokenizer, M2M100ForConditionalGeneration
from marian import LANGUAGE_CODES

# Cache for loaded models
MODEL_CACHE = {}
NLLB_MODEL_CACHE = {}
M2M_MODEL_CACHE = {}

# NLLB-200 model configuration
NLLB_MODEL_NAME = "facebook/nllb-200-distilled-600M"
NLLB_ARABIC = "arb_Arab"
NLLB_ENGLISH = "eng_Latn"

# M2M-100 model configuration (better quality for many language pairs)
M2M_MODEL_NAME = "facebook/m2m100_418M"
M2M_LANG_CODES = {
    "english": "en",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "arabic": "ar",
}


def load_nllb_model():
    """Load NLLB-200 model and tokenizer with caching."""
    if "nllb" in NLLB_MODEL_CACHE:
        return NLLB_MODEL_CACHE["nllb"]
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(NLLB_MODEL_NAME, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL_NAME, local_files_only=True)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(NLLB_MODEL_NAME)
        model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL_NAME)
    
    NLLB_MODEL_CACHE["nllb"] = (tokenizer, model)
    return tokenizer, model


def load_m2m_model():
    """Load M2M-100 model and tokenizer with caching (high quality multilingual)."""
    if "m2m" in M2M_MODEL_CACHE:
        return M2M_MODEL_CACHE["m2m"]
    
    try:
        tokenizer = M2M100Tokenizer.from_pretrained(M2M_MODEL_NAME, local_files_only=True)
        model = M2M100ForConditionalGeneration.from_pretrained(M2M_MODEL_NAME, local_files_only=True)
    except Exception:
        tokenizer = M2M100Tokenizer.from_pretrained(M2M_MODEL_NAME)
        model = M2M100ForConditionalGeneration.from_pretrained(M2M_MODEL_NAME)
    
    M2M_MODEL_CACHE["m2m"] = (tokenizer, model)
    return tokenizer, model


def detect_language(text: str) -> str:
    """Detect if text is Arabic or English."""
    return "arabic" if any("\u0600" <= c <= "\u06FF" for c in text) else "english"


def translate_nllb(text: str) -> str:
    """Translate between Arabic and English using NLLB-200."""
    tokenizer, model = load_nllb_model()
    lang = detect_language(text)
    
    if lang == "arabic":
        src = NLLB_ARABIC
        tgt = NLLB_ENGLISH
    else:
        src = NLLB_ENGLISH
        tgt = NLLB_ARABIC
    
    inputs = tokenizer(text, return_tensors="pt")
    generated = model.generate(
        **inputs,
        forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt)
    )
    return tokenizer.decode(generated[0], skip_special_tokens=True)


def translate_m2m(text: str, src_lang: str, tgt_lang: str) -> str:
    """Translate using M2M-100 (high quality for many language pairs)."""
    tokenizer, model = load_m2m_model()
    
    src_code = M2M_LANG_CODES.get(src_lang.lower())
    tgt_code = M2M_LANG_CODES.get(tgt_lang.lower())
    
    if not src_code or not tgt_code:
        raise ValueError(f"M2M languages not supported: {src_lang}, {tgt_lang}")
    
    # Set source language
    tokenizer.src_lang = src_code
    
    # Tokenize and translate
    inputs = tokenizer(text, return_tensors="pt")
    generated_tokens = model.generate(**inputs, forced_bos_token_id=tokenizer.get_lang_id(tgt_code))
    
    return tokenizer.decode(generated_tokens[0], skip_special_tokens=True)


def load_model_pair(src_lang: str, tgt_lang: str):
    """Load Marian translation model pair with caching."""
    src_code = LANGUAGE_CODES.get(src_lang.lower())
    tgt_code = LANGUAGE_CODES.get(tgt_lang.lower())
    if not src_code or not tgt_code:
        raise ValueError(f"Languages not supported: {src_lang}, {tgt_lang}")

    model_name = f"Helsinki-NLP/opus-mt-{src_code}-{tgt_code}"
    if model_name in MODEL_CACHE:
        return MODEL_CACHE[model_name]

    try:
        tokenizer = MarianTokenizer.from_pretrained(model_name, local_files_only=True)
        model = MarianMTModel.from_pretrained(model_name, local_files_only=True)
    except Exception:
        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)

    MODEL_CACHE[model_name] = (tokenizer, model)
    return tokenizer, model


def translate_text(text: str, src_lang: str, tgt_lang: str) -> str:
    """Translate text from source to target language.
    
    Uses M2M-100 for high quality (recommended).
    Falls back to Marian if M2M doesn't support the language pair.
    """
    src_lower = src_lang.lower()
    tgt_lower = tgt_lang.lower()
    
    # Try M2M-100 first (better quality for most pairs)
    if src_lower in M2M_LANG_CODES and tgt_lower in M2M_LANG_CODES:
        try:
            return translate_m2m(text, src_lang, tgt_lang)
        except Exception as e:
            print(f"M2M translation failed, falling back to Marian: {str(e)}")
    
    # Fall back to Marian for other language pairs
    try:
        tokenizer, model = load_model_pair(src_lang, tgt_lang)
        inputs = tokenizer(text, return_tensors="pt", padding=True)
        outputs = model.generate(**inputs)
        return tokenizer.decode(outputs[0], skip_special_tokens=True)
    except Exception as e:
        raise RuntimeError(f"Translation failed for {src_lang}→{tgt_lang}: {str(e)}")


def translate_with_score(text: str, src_lang: str, tgt_lang: str) -> tuple:
    """Translate text and return (translation, confidence_score).
    
    Confidence is based on:
    - Model used (M2M-100 = 0.95, Marian = 0.85)
    - Text length (longer = more confident, cap at 100)
    - Language pair support
    
    Returns:
        (translation_text, confidence_score: 0.0-1.0)
    """
    src_lower = src_lang.lower()
    tgt_lower = tgt_lang.lower()
    
    # Base score per model
    model_score = 0.85  # Marian default
    translation = None
    
    # Try M2M-100 first (higher confidence model)
    if src_lower in M2M_LANG_CODES and tgt_lower in M2M_LANG_CODES:
        try:
            translation = translate_m2m(text, src_lang, tgt_lang)
            model_score = 0.95  # M2M-100 has better quality
        except Exception as e:
            print(f"M2M translation failed, falling back to Marian: {str(e)}")
    
    # Fall back to Marian if needed
    if translation is None:
        try:
            tokenizer, model = load_model_pair(src_lang, tgt_lang)
            inputs = tokenizer(text, return_tensors="pt", padding=True)
            outputs = model.generate(**inputs)
            translation = tokenizer.decode(outputs[0], skip_special_tokens=True)
            model_score = 0.85  # Marian baseline
        except Exception as e:
            raise RuntimeError(f"Translation failed for {src_lang}→{tgt_lang}: {str(e)}")
    
    # Adjust score based on text length
    # Longer text = more context = higher confidence (but cap at 100)
    text_len = len(text.split())
    length_bonus = min(0.10, text_len * 0.01)  # +0% to +10% based on word count
    
    # Language pair bonus (some pairs are more reliable)
    pair_key = f"{src_lower}-{tgt_lower}"
    supported_pairs = {
        "english-arabic": 0.95,
        "arabic-english": 0.95,
        "english-french": 0.98,
        "french-english": 0.98,
        "english-spanish": 0.98,
        "spanish-english": 0.98,
    }
    pair_bonus = (supported_pairs.get(pair_key, 0.0) - model_score) * 0.5
    
    # Final confidence score (0.0 - 1.0)
    confidence = min(1.0, model_score + length_bonus + pair_bonus)
    
    return translation, confidence

