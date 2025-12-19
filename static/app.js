const chat = document.getElementById('chat');
const form = document.getElementById('composer');
const input = document.getElementById('message');
const source = document.getElementById('source');
const target = document.getElementById('target');
const chatsList = document.getElementById('chats');
const newChatBtn = document.getElementById('new-chat');
const showActiveBtn = document.getElementById('show-active');
const showArchivedBtn = document.getElementById('show-archived');
const micBtn = document.getElementById('mic-btn');
const autoSpeakCheckbox = document.getElementById('auto-speak');
const fileInput = document.getElementById('file-input');
const fileBtn = document.getElementById('file-btn');
const themeToggle = document.getElementById('theme-toggle');

// -----------------------
// Theme Toggle
// -----------------------
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'dark';
  document.body.classList.toggle('light-theme', savedTheme === 'light');
  updateThemeButton();
}

function toggleTheme() {
  const isLight = document.body.classList.toggle('light-theme');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeButton();
}

function updateThemeButton() {
  if (themeToggle) {
    themeToggle.textContent = document.body.classList.contains('light-theme') ? '🌙' : '☀️';
  }
}

if (themeToggle) {
  themeToggle.addEventListener('click', toggleTheme);
}

// Initialize theme on page load
initTheme();

let currentSessionId = null;
let sessionsCache = [];

async function loadSessions() {
  try {
    const res = await fetch('/api/sessions');
    const data = await res.json();
    sessionsCache = data.sessions || [];
    return sessionsCache;
  } catch (err) {
    console.error('Failed to load sessions:', err);
    return [];
  }
}

function getCurrentSessionId() {
  return currentSessionId;
}

function setCurrentSessionId(id) {
  currentSessionId = id;
}

async function createSession() {
  try {
    const res = await fetch('/api/sessions', { method: 'POST' });
    const session = await res.json();
    if (res.ok) {
      sessionsCache.unshift(session);
      setCurrentSessionId(session.id);
      return session;
    }
    throw new Error('Failed to create session');
  } catch (err) {
    console.error('Failed to create session:', err);
    return null;
  }
}

async function updateSession(id, updates) {
  try {
    const res = await fetch(`/api/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
    if (res.ok) {
      const updated = await res.json();
      const idx = sessionsCache.findIndex(s => s.id === id);
      if (idx !== -1) {
        sessionsCache[idx] = { ...sessionsCache[idx], ...updated };
      }
    }
  } catch (err) {
    console.error('Failed to update session:', err);
  }
}

async function deleteSession(id) {
  try {
    const res = await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
    if (res.ok) {
      sessionsCache = sessionsCache.filter(s => s.id !== id);
      if (getCurrentSessionId() === id) {
        setCurrentSessionId(sessionsCache[0]?.id || '');
      }
    }
  } catch (err) {
    console.error('Failed to delete session:', err);
  }
}

async function addMessageToSession(sessionId, role, text) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, text })
    });
    return res.ok;
  } catch (err) {
    console.error('Failed to add message:', err);
    return false;
  }
}

async function loadSessionMessages(sessionId) {
  try {
    const res = await fetch(`/api/sessions/${sessionId}/messages`);
    const data = await res.json();
    return data.messages || [];
  } catch (err) {
    console.error('Failed to load messages:', err);
    return [];
  }
}

// -----------------------
// Rendering helpers
// -----------------------
function clearChat() {
  chat.innerHTML = '';
}

function getSpeechLangForTarget(targetName) {
  const map = {
    english: 'en-US',
    arabic: 'ar-SA',
    french: 'fr-FR',
    spanish: 'es-ES',
    german: 'de-DE',
    italian: 'it-IT',
    portuguese: 'pt-PT',
    russian: 'ru-RU',
    japanese: 'ja-JP',
    chinese: 'zh-CN',
    korean: 'ko-KR',
    hindi: 'hi-IN',
    turkish: 'tr-TR',
    dutch: 'nl-NL',
    swedish: 'sv-SE',
    norwegian: 'nb-NO',
    danish: 'da-DK',
    finnish: 'fi-FI',
    greek: 'el-GR',
    polish: 'pl-PL',
    czech: 'cs-CZ',
    ukrainian: 'uk-UA',
    romanian: 'ro-RO'
  };
  return map[(targetName || '').toLowerCase()] || 'en-US';
}

let loadedVoices = [];
function refreshVoices() {
  if (!('speechSynthesis' in window)) return [];
  const v = window.speechSynthesis.getVoices() || [];
  if (v.length > 0) loadedVoices = v;
  return loadedVoices;
}
window.speechSynthesis?.addEventListener?.('voiceschanged', refreshVoices);
refreshVoices();

function canUseWebTTS() {
  return 'speechSynthesis' in window && typeof window.SpeechSynthesisUtterance !== 'undefined';
}

async function speak(text, lang) {
  try {
    if (canUseWebTTS()) {
      try { window.speechSynthesis.cancel(); } catch (_) {}
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = lang || 'en-US';
      const voices = refreshVoices();
      if (voices && voices.length) {
        const exact = voices.find(v => v.lang === utter.lang);
        const loose = voices.find(v => v.lang?.startsWith(utter.lang.split('-')[0]));
        const chosen = exact || loose;
        if (chosen) utter.voice = chosen;
      }
      window.speechSynthesis.speak(utter);
      return;
    }
  } catch (_) {
    // fall through to server TTS
  }

  // Fallback: server-side TTS
  try {
    const res = await fetch('/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, lang: lang || 'en-US' })
    });
    if (!res.ok) throw new Error('TTS failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    await audio.play();
  } catch (err) {
    // no-op: silent failure
  }
}

function addBubble(text, role) {
  const div = document.createElement('div');
  div.className = `bubble ${role}`;
  div.textContent = text;
  if (role === 'assistant') {
    const btn = document.createElement('button');
    btn.className = 'play-btn';
    btn.type = 'button';
    btn.textContent = '▶';
    btn.title = 'Play';
    btn.addEventListener('click', () => {
      const lang = getSpeechLangForTarget(target.value);
      speak(text, lang);
    });
    div.appendChild(btn);
  }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function addBubbleWithScore(text, role, confidence) {
  const div = document.createElement('div');
  div.className = `bubble ${role}`;
  div.textContent = text;
  if (role === 'assistant') {
    const btn = document.createElement('button');
    btn.className = 'play-btn';
    btn.type = 'button';
    btn.textContent = '▶';
    btn.title = 'Play';
    btn.addEventListener('click', () => {
      const lang = getSpeechLangForTarget(target.value);
      speak(text, lang);
    });
    div.appendChild(btn);
  }
  
  // Add confidence score if provided
  if (typeof confidence === 'number') {
    const scoreEl = document.createElement('div');
    scoreEl.className = 'quality-score';
    const scoreColor = confidence >= 90 ? '🟢' : confidence >= 75 ? '🟡' : '🔴';
    scoreEl.textContent = `${scoreColor} Quality: ${confidence}%`;
    div.appendChild(scoreEl);
  }
  
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function renderChat(sessionId) {
  clearChat();
  if (!sessionId) return;
  const messages = await loadSessionMessages(sessionId);
  for (const m of messages) {
    addBubble(m.text, m.role);
  }
}

function setActiveFilter(filter) {
  const isArchived = filter === 'archived';
  showActiveBtn.classList.toggle('active', !isArchived);
  showArchivedBtn.classList.toggle('active', isArchived);
  renderChatList(filter);
}

async function renderChatList(filter = 'active') {
  const sessions = await loadSessions();
  const currentId = getCurrentSessionId();
  const filtered = sessions.filter(s => (filter === 'archived' ? s.archived : !s.archived));
  chatsList.innerHTML = '';
  for (const s of filtered) {
    const li = document.createElement('li');
    li.className = 'chat-item' + (s.id === currentId ? ' active' : '');
    li.dataset.id = s.id;

    const title = document.createElement('div');
    title.className = 'chat-title';
    title.textContent = s.title || 'Untitled';
    li.appendChild(title);

    const actions = document.createElement('div');
    actions.className = 'chat-actions';

    const archiveBtn = document.createElement('button');
    archiveBtn.className = 'icon-btn';
    archiveBtn.title = s.archived ? 'Unarchive' : 'Archive';
    archiveBtn.textContent = s.archived ? 'Unarchive' : 'Archive';
    archiveBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await updateSession(s.id, { archived: !s.archived });
      // If we archived the current session while viewing active, move selection.
      const filterNow = showArchivedBtn.classList.contains('active') ? 'archived' : 'active';
      if (filterNow === 'active' && getCurrentSessionId() === s.id) {
        const remaining = sessions.find(x => !x.archived && x.id !== s.id);
        setCurrentSessionId(remaining?.id || '');
        renderCurrentSession();
      }
      renderChatList(filterNow);
    });
    actions.appendChild(archiveBtn);

    const delBtn = document.createElement('button');
    delBtn.className = 'icon-btn';
    delBtn.title = 'Delete';
    delBtn.textContent = 'Delete';
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (confirm('Delete this chat? This cannot be undone.')) {
        const id = s.id;
        await deleteSession(id);
        renderChatList(showArchivedBtn.classList.contains('active') ? 'archived' : 'active');
        renderCurrentSession();
      }
    });
    actions.appendChild(delBtn);

    li.appendChild(actions);

    li.addEventListener('click', async () => {
      setCurrentSessionId(s.id);
      renderChatList(showArchivedBtn.classList.contains('active') ? 'archived' : 'active');
      renderCurrentSession();
    });

    chatsList.appendChild(li);
  }
}

async function renderCurrentSession() {
  const currentId = getCurrentSessionId();
  await renderChat(currentId);
}

async function ensureSession() {
  let id = getCurrentSessionId();
  if (!id) {
    const session = await createSession();
    if (session) {
      await renderChatList(showArchivedBtn.classList.contains('active') ? 'archived' : 'active');
      return session;
    }
    return null;
  }
  return { id };
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  const session = await ensureSession();
  if (!session) return;
  
  // Append user message
  addBubble(text, 'user');
  await addMessageToSession(session.id, 'user', text);
  await renderChatList(showArchivedBtn.classList.contains('active') ? 'archived' : 'active');
  input.value = '';

  const src = source.value;
  const tgt = target.value;
  addBubble('Translating...', 'system');
  try {
    const res = await fetch('/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source: src, target: tgt })
    });
    const data = await res.json();
    const last = chat.querySelector('.bubble.system:last-child');
    if (last) last.remove();
    if (data.translation) {
      addBubbleWithScore(data.translation, 'assistant', data.confidence);
      await addMessageToSession(session.id, 'assistant', data.translation);
      if (autoSpeakCheckbox?.checked) {
        const lang = getSpeechLangForTarget(target.value);
        speak(data.translation, lang);
      }
    } else {
      addBubble(data.error || 'Unknown error', 'error');
    }
  } catch (err) {
    const last = chat.querySelector('.bubble.system:last-child');
    if (last) last.remove();
    addBubble('Network error. Is the server running?', 'error');
  }
});

// -----------------------
// UI wiring
// -----------------------
newChatBtn?.addEventListener('click', async () => {
  const session = await createSession();
  if (session) {
    await renderChatList(showArchivedBtn.classList.contains('active') ? 'archived' : 'active');
    await renderCurrentSession();
  }
});

showActiveBtn?.addEventListener('click', () => setActiveFilter('active'));
showArchivedBtn?.addEventListener('click', () => setActiveFilter('archived'));

// Speech recognition (Web Speech API)
let recognition;
let recognizing = false;
function getRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  if (!recognition) {
    recognition = new SR();
    recognition.lang = getSpeechLangForTarget(source.value);
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (e) => {
      const transcript = Array.from(e.results).map(r => r[0].transcript).join(' ');
      if (transcript) {
        input.value = transcript;
        // Auto send after capture
        form.requestSubmit();
      }
    };
    recognition.onerror = () => {
      micBtn?.classList.remove('recording');
      recognizing = false;
    };
    recognition.onend = () => {
      micBtn?.classList.remove('recording');
      recognizing = false;
    };
  }
  return recognition;
}

micBtn?.addEventListener('click', () => {
  const rec = getRecognition();
  if (!rec) {
    alert('Speech recognition not supported by this browser. Try Chrome.');
    return;
  }
  rec.lang = getSpeechLangForTarget(source.value);
  if (!recognizing) {
    try {
      rec.start();
      recognizing = true;
      micBtn.classList.add('recording');
    } catch (_) {
      // ignore start errors
    }
  } else {
    try {
      rec.stop();
    } catch (_) {
      // ignore stop errors
    }
  }
});

// Initial boot
(async () => {
  // Load sessions and create one if needed
  const sessions = await loadSessions();
  if (sessions.length === 0) {
    await createSession();
  } else if (!getCurrentSessionId()) {
    setCurrentSessionId(sessions[0].id);
  }
  setActiveFilter('active');
  await renderCurrentSession();
})();

// -----------------------
// File translate (in-chat)
// -----------------------
fileBtn?.addEventListener('click', () => fileInput?.click());

fileInput?.addEventListener('change', async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  e.target.value = '';
  const session = await ensureSession();
  if (!session) return;
  
  // Show filename as a user message
  const userText = `Uploaded file: ${file.name}`;
  addBubble(userText, 'user');
  await addMessageToSession(session.id, 'user', userText);
  await renderChatList(showArchivedBtn.classList.contains('active') ? 'archived' : 'active');

  // System bubble while uploading/translating
  addBubble('Translating file...', 'system');
  let sys = chat.querySelector('.bubble.system:last-child');
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source', source.value);
    formData.append('target', target.value);
    const res = await fetch('/translate_file', { method: 'POST', body: formData });
    const data = await res.json();
    if (sys) sys.remove();
    if (!res.ok) {
      addBubble(data.error || 'Failed to translate file', 'error');
      return;
    }
    const translated = data.translated || '';
    addBubble(translated, 'assistant');
    await addMessageToSession(session.id, 'assistant', translated);
    if (autoSpeakCheckbox?.checked) {
      const lang = getSpeechLangForTarget(target.value);
      speak(translated, lang);
    }
  } catch (err) {
    if (sys) sys.remove();
    addBubble('Network error while uploading file.', 'error');
  }
});

// -----------------------
// Image OCR (in-chat)
// -----------------------
const imageBtn = document.getElementById('image-btn');
const imageInput = document.getElementById('image-input');

imageBtn?.addEventListener('click', () => imageInput?.click());

imageInput?.addEventListener('change', async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  e.target.value = '';
  const session = await ensureSession();
  if (!session) return;
  
  // Show filename as a user message
  const userText = `Uploaded image: ${file.name}`;
  addBubble(userText, 'user');
  await addMessageToSession(session.id, 'user', userText);
  await renderChatList(showArchivedBtn.classList.contains('active') ? 'archived' : 'active');

  // System bubble while processing
  addBubble('Extracting text from image...', 'system');
  let sys = chat.querySelector('.bubble.system:last-child');
  
  try {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('target', target.value);
    
    const res = await fetch('/ocr', { method: 'POST', body: formData });
    const data = await res.json();
    if (sys) sys.remove();
    
    if (!res.ok) {
      addBubble(data.error || 'Failed to process image', 'error');
      return;
    }
    
    // Show extracted text
    const extracted = data.extracted_text || '';
    addBubble(`📜 Extracted text:\n${extracted}`, 'assistant');
    await addMessageToSession(session.id, 'assistant', `Extracted: ${extracted}`);
    
    // Show translated text if available
    if (data.translated_text) {
      const translated = data.translated_text;
      addBubble(`🔄 Translated to ${target.value}:\n${translated}`, 'assistant');
      await addMessageToSession(session.id, 'assistant', `Translated: ${translated}`);
      
      if (autoSpeakCheckbox?.checked) {
        const lang = getSpeechLangForTarget(target.value);
        speak(translated, lang);
      }
    } else if (data.translation_error) {
      addBubble(`Translation error: ${data.translation_error}`, 'system');
    }
    
  } catch (err) {
    if (sys) sys.remove();
    addBubble('Network error while processing image.', 'error');
  }
});

