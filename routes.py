"""Flask routes for authentication, chat, translation, and TTS."""

from flask import request, jsonify, render_template, send_file, redirect, url_for, session
from werkzeug.utils import secure_filename
import os
import datetime as dt
import io

from models import User, ChatSession, ChatMessage, get_db
from translation import translate_text, translate_with_score
from tts import synthesize_tts
from marian import LANGUAGE_CODES

from ocr import extract_text_from_image, detect_language_from_text
from logger import logger



def register_routes(app):
    """Register all routes with the Flask app."""

    # =====================
    # Page Routes
    # =====================

    @app.get("/")
    def index():
        return redirect(url_for('welcome_page'))

    @app.get("/app")
    def app_home():
        if not session.get('user_id'):
            return redirect(url_for('login_page'))
        user_ctx = None
        try:
            uid = session.get('user_id')
            if uid:
                with get_db() as db:
                    u = db.query(User).filter(User.id == uid).first()
                    if u:
                        user_ctx = {"id": u.id, "name": u.name, "email": u.email}
        except Exception:
            user_ctx = None
        return render_template("index.html", languages=list(LANGUAGE_CODES.keys()), user=user_ctx)

    @app.get("/welcome")
    def welcome_page():
        return render_template("welcome.html")

    @app.get("/login")
    def login_page():
        return render_template("login.html")

    @app.get("/signup")
    def signup_page():
        return render_template("signup.html")

    # =====================
    # Authentication Routes
    # =====================

    @app.post("/signup")
    def signup_post():
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        
        if not name or not email or not password:
            return render_template("signup.html", error="All fields are required", name=name, email=email), 400
        if len(password) < 8:
            return render_template("signup.html", error="Password must be at least 8 characters", name=name, email=email), 400
        
        with get_db() as db:
            exists = db.query(User).filter(User.email == email).first()
            if exists:
                return render_template("signup.html", error="Email already registered", name=name, email=email), 400
            user = User(name=name, email=email, password_hash=User.hash_password(password))
            db.add(user)
            db.commit()
            session['user_id'] = user.id
        
        return redirect(url_for('login_page'))

    @app.post("/login")
    def login_post():
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        
        with get_db() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user or not user.check_password(password):
                return render_template("login.html", error="Invalid email or password", email=email), 401
            session['user_id'] = user.id
        
        return redirect(url_for('app_home'))

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for('welcome_page'))

    # =====================
    # Chat Session API
    # =====================

    @app.get("/api/sessions")
    def get_sessions():
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"sessions": []})
        
        with get_db() as db:
            sessions = db.query(ChatSession).filter(
                ChatSession.user_id == user_id,
                ChatSession.archived == False
            ).order_by(ChatSession.updated_at.desc()).all()
            
            return jsonify({
                "sessions": [{
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat()
                } for s in sessions]
            })

    @app.post("/api/sessions")
    def create_session():
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        session_id = f"s_{int(dt.datetime.utcnow().timestamp() * 1000)}"
        with get_db() as db:
            chat_session = ChatSession(
                id=session_id,
                user_id=user_id,
                title="New chat"
            )
            db.add(chat_session)
            db.commit()
            
            return jsonify({
                "id": session_id,
                "title": "New chat",
                "created_at": chat_session.created_at.isoformat(),
                "updated_at": chat_session.updated_at.isoformat()
            })

    @app.get("/api/sessions/<session_id>/messages")
    def get_session_messages(session_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        with get_db() as db:
            chat_session = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id
            ).first()
            
            if not chat_session:
                return jsonify({"error": "Session not found"}), 404
            
            messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            return jsonify({
                "messages": [{
                    "role": m.role,
                    "text": m.text,
                    "created_at": m.created_at.isoformat()
                } for m in messages]
            })

    @app.post("/api/sessions/<session_id>/messages")
    def add_message(session_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.get_json()
        role = data.get('role', 'user')
        text = data.get('text', '')
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        with get_db() as db:
            chat_session = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id
            ).first()
            
            if not chat_session:
                return jsonify({"error": "Session not found"}), 404
            
            message = ChatMessage(
                session_id=session_id,
                role=role,
                text=text
            )
            db.add(message)
            
            # Update session title if it's still "New chat" and this is a user message
            if chat_session.title == "New chat" and role == "user":
                chat_session.title = text[:30] + "…" if len(text) > 30 else text
            
            db.commit()
            
            return jsonify({
                "id": message.id,
                "role": message.role,
                "text": message.text,
                "created_at": message.created_at.isoformat()
            })

    @app.patch("/api/sessions/<session_id>")
    def update_session(session_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.get_json()
        with get_db() as db:
            chat_session = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id
            ).first()
            
            if not chat_session:
                return jsonify({"error": "Session not found"}), 404
            
            if 'title' in data:
                chat_session.title = data['title']
            if 'archived' in data:
                chat_session.archived = data['archived']
            
            db.commit()
            
            return jsonify({
                "id": chat_session.id,
                "title": chat_session.title,
                "archived": chat_session.archived
            })

    @app.delete("/api/sessions/<session_id>")
    def delete_session(session_id):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        with get_db() as db:
            chat_session = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id
            ).first()
            
            if not chat_session:
                return jsonify({"error": "Session not found"}), 404
            
            # Delete all messages first
            db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
            # Delete the session
            db.delete(chat_session)
            db.commit()
            
            return jsonify({"success": True})

    # =====================
    # Translation Routes
    # =====================

    @app.post("/translate")
    def translate_route():
        data = request.get_json(force=True)
        text = data.get("text", "").strip()
        src_lang = data.get("source", "").strip()
        tgt_lang = data.get("target", "").strip()

        if not text:
            return jsonify({"error": "Text is required"}), 400
        if not src_lang or not tgt_lang:
            return jsonify({"error": "Source and target languages are required"}), 400

        try:
            translation, confidence = translate_with_score(text, src_lang, tgt_lang)
            return jsonify({
                "translation": translation,
                "confidence": round(confidence * 100, 1)  # Return as percentage
            })
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({
                "error": "Failed to translate. If offline, pre-download the model or check network.",
                "details": str(e)
            }), 500

    @app.post("/translate_file")
    def translate_file_route():
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        src_lang = (request.form.get('source') or '').strip()
        tgt_lang = (request.form.get('target') or '').strip()
        if not src_lang or not tgt_lang:
            return jsonify({"error": "Source and target languages are required"}), 400

        f = request.files['file']
        filename = secure_filename(f.filename or 'input.txt')
        allowed = {'.txt', '.md', '.csv', '.srt', '.vtt', '.json', '.xml', '.html'}
        _, ext = os.path.splitext(filename)
        
        if ext.lower() not in allowed:
            return jsonify({"error": "Unsupported file type"}), 400
        
        try:
            # Read as text (utf-8), fallback to latin-1 if decoding fails
            try:
                content = f.read().decode('utf-8')
            except Exception:
                f.stream.seek(0)
                content = f.read().decode('latin-1', errors='ignore')

            if not content.strip():
                return jsonify({"error": "File is empty"}), 400

            translated = translate_text(content, src_lang, tgt_lang)
            return jsonify({
                "filename": filename,
                "translated": translated
            })
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "Failed to translate file", "details": str(e)}), 500

    # =====================
    # Text-to-Speech Route
    # =====================

    @app.post("/tts")
    def tts_route():
        data = request.get_json(force=True)
        text = str(data.get("text", "")).strip()
        lang = str(data.get("lang", "")).strip() or "en-US"
        
        if not text:
            return jsonify({"error": "Text is required"}), 400

        try:
            audio_bytes, mime_type = synthesize_tts(text, lang)
            return send_file(io.BytesIO(audio_bytes), mimetype=mime_type)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 501
        except Exception as e:
            return jsonify({"error": "TTS synthesis failed", "details": str(e)}), 500

    # =====================
    # OCR & Image Translation
    # =====================


    @app.post("/ocr")
    def ocr_route():
        """Extract text from image and optionally translate it. Logs errors and analytics."""
        logger.info("/ocr endpoint called")
        if 'image' not in request.files:
            logger.warning("No image uploaded in request")
            return jsonify({"error": "No image uploaded"}), 400

        image_file = request.files['image']
        if not image_file or image_file.filename == '':
            logger.warning("No image selected for upload")
            return jsonify({"error": "No image selected"}), 400

        # Check file type
        allowed_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        _, ext = os.path.splitext(image_file.filename or '')
        if ext.lower() not in allowed_exts:
            logger.warning(f"Unsupported image format: {ext}")
            return jsonify({"error": "Unsupported image format. Use: JPG, PNG, GIF, BMP, WebP"}), 400

        try:
            # Read image bytes
            image_bytes = image_file.read()
            logger.info(f"Image uploaded: {image_file.filename}, size: {len(image_bytes)} bytes")

            # Extract text using OCR
            try:
                extracted_text = extract_text_from_image(image_bytes)
                logger.info(f"OCR success for {image_file.filename}")
            except Exception as ocr_err:
                logger.error(f"OCR failed for {image_file.filename}: {ocr_err}")
                raise

            # Check if translation requested
            tgt_lang = (request.form.get('target') or '').strip()

            response = {
                "extracted_text": extracted_text,
                "detected_language": detect_language_from_text(extracted_text)
            }

            # Translate if target language specified
            if tgt_lang:
                try:
                    src_lang = detect_language_from_text(extracted_text)
                    translated = translate_text(extracted_text, src_lang, tgt_lang)
                    response["translated_text"] = translated
                    logger.info(f"Translation success: {src_lang} -> {tgt_lang}")
                except Exception as e:
                    response["translation_error"] = str(e)
                    logger.error(f"Translation failed: {e}")

            # Analytics: log extracted text length
            logger.info(f"Extracted text length: {len(extracted_text)}")

            return jsonify(response)

        except RuntimeError as e:
            logger.error(f"OCR RuntimeError: {e}")
            return jsonify({"error": str(e)}), 501
        except Exception as e:
            logger.exception(f"OCR processing failed: {e}")
            return jsonify({"error": "OCR processing failed", "details": str(e)}), 500

