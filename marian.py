# chat_marian_translator.py

from transformers import MarianMTModel, MarianTokenizer

# 1️⃣ Language mapping

LANGUAGE_CODES = {
    "english": "en",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "arabic": "ar"
}

# 2️⃣ Load model for given source and target language
MODEL_CACHE = {}

def load_model(src_lang, tgt_lang):
    src_code = LANGUAGE_CODES.get(src_lang.lower())
    tgt_code = LANGUAGE_CODES.get(tgt_lang.lower())
    if not src_code or not tgt_code:
        raise ValueError(f"Languages not supported: {src_lang}, {tgt_lang}")

    model_name = f"Helsinki-NLP/opus-mt-{src_code}-{tgt_code}"

    # Cache models to avoid reloading
    if model_name in MODEL_CACHE:
        return MODEL_CACHE[model_name]

    # First, try to load from local cache only (works offline)
    try:
        tokenizer = MarianTokenizer.from_pretrained(model_name, local_files_only=True)
        model = MarianMTModel.from_pretrained(model_name, local_files_only=True)
    except Exception:
        # If not available locally, attempt to download from the Hub
        try:
            tokenizer = MarianTokenizer.from_pretrained(model_name)
            model = MarianMTModel.from_pretrained(model_name)
        except Exception as e:
            raise RuntimeError(
                "Failed to load model. No local files found and download failed. "
                "If you're offline, pre-download the model with: \n"
                "  huggingface-cli download Helsinki-NLP/opus-mt-" + src_code + "-" + tgt_code + " --local-dir ./.hf_models/opus-mt-" + src_code + "-" + tgt_code + "\n"
                "Then set the HF_HOME or TRANSFORMERS_CACHE to that directory, or update the code to point there.\n"
                "If you're online, please check your DNS/connection and try again."
            ) from e
    MODEL_CACHE[model_name] = (tokenizer, model)
    return tokenizer, model


# 3️⃣ Translation function
def translate(text, tokenizer, model):
    inputs = tokenizer(text, return_tensors="pt", padding=True)
    translated = model.generate(**inputs)
    return tokenizer.decode(translated[0], skip_special_tokens=True)

# 4️⃣ Chat loop
def chat():
    print("=== Chat Translator (MarianMT) ===")
    print(f"Supported languages: {', '.join(LANGUAGE_CODES.keys())}")
    print("You can change languages anytime by typing 'change'\n")
    
    src_lang = input("Source language: ").strip()
    tgt_lang = input("Target language: ").strip()

    try:
        tokenizer, model = load_model(src_lang, tgt_lang)
        print(f"\nModel loaded for {src_lang} → {tgt_lang}!\n")
    except (ValueError, RuntimeError) as e:
        print(e)
        return

    while True:
        text = input(f"{src_lang.title()} text (type 'exit' to quit, 'change' to change languages): ").strip()
        
        if text.lower() == "exit":
            print("Exiting chat. Goodbye!")
            break
        
        if text.lower() == "change":
            src_lang = input("New source language: ").strip()
            tgt_lang = input("New target language: ").strip()
            try:
                tokenizer, model = load_model(src_lang, tgt_lang)
                print(f"Model updated for {src_lang} → {tgt_lang}!\n")
            except (ValueError, RuntimeError) as e:
                print(e)
            continue

        translation = translate(text, tokenizer, model)
        print(f"{tgt_lang.title()}: {translation}\n")

if __name__ == "__main__":
    chat()
