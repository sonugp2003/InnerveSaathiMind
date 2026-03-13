const chatLog = document.getElementById('chat-log');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatLanguage = document.getElementById('chat-language');
const chatActions = document.getElementById('chat-actions');
const emergencyBanner = document.getElementById('emergency-banner');
const engineStatus = document.getElementById('engine-status');

const moodSlider = document.getElementById('mood');
const moodValue = document.getElementById('mood-value');
const checkinForm = document.getElementById('checkin-form');
const checkinResult = document.getElementById('checkin-result');

const resourceForm = document.getElementById('resource-form');
const resourceList = document.getElementById('resource-list');

const quickPrompts = document.getElementById('quick-prompts');

const history = [];
const API_BASE = (window.SAATHIMIND_API_BASE || '').replace(/\/+$/, '');

function apiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

appendMessage('assistant', 'Hi, I am SaathiMind. You can share anything here. What has been weighing on you today?');

moodSlider.addEventListener('input', () => {
  moodValue.textContent = moodSlider.value;
});

quickPrompts.addEventListener('click', (event) => {
  const btn = event.target.closest('button[data-prompt]');
  if (!btn) return;
  chatInput.value = btn.dataset.prompt;
  chatInput.focus();
});

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  appendMessage('user', message);
  chatInput.value = '';
  const pendingBubble = appendMessage('assistant pending', 'SaathiMind is reflecting...');

  try {
    const payload = {
      language: chatLanguage.value,
      message,
      history: history.slice(-6),
    };

    const response = await fetch(apiUrl('/api/chat'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    pendingBubble.className = 'bubble assistant';
    pendingBubble.textContent = data.reply || 'I am here with you.';
    renderActions(data.suggested_actions || []);
    toggleEmergency(Boolean(data.escalate));
  } catch (error) {
    pendingBubble.className = 'bubble assistant';
    pendingBubble.textContent = 'I could not reach support services right now. Please try again.';
  }
});

checkinForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const stressorsRaw = document.getElementById('stressors').value;
  const note = document.getElementById('note').value.trim();
  const stressors = stressorsRaw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  try {
    const response = await fetch(apiUrl('/api/check-in'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mood: Number(moodSlider.value),
        stressors,
        note,
        language: chatLanguage.value,
      }),
    });

    const data = await response.json();
    renderCheckin(data);
    toggleEmergency(Boolean(data.escalate));
  } catch (error) {
    checkinResult.innerHTML = '<p>Could not generate check-in plan. Please retry.</p>';
  }
});

resourceForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  await loadResources();
});

async function loadResources() {
  const query = document.getElementById('resource-query').value.trim();
  const mode = document.getElementById('resource-mode').value;
  const language = document.getElementById('resource-language').value;

  const params = new URLSearchParams();
  if (query) params.set('q', query);
  if (mode) params.set('mode', mode);
  if (language) params.set('language', language);

  resourceList.innerHTML = '<p>Loading trusted resources...</p>';

  try {
    const response = await fetch(apiUrl(`/api/resources?${params.toString()}`));
    const data = await response.json();
    renderResources(data.resources || []);
  } catch (error) {
    resourceList.innerHTML = '<p>Could not load resources. Try again.</p>';
  }
}

async function loadHealth() {
  try {
    const response = await fetch(apiUrl('/api/health'));
    const data = await response.json();
    if (data.vertex_enabled) {
      engineStatus.textContent = `AI Engine: Vertex (${data.vertex_model})`;
    } else {
      engineStatus.textContent = 'AI Engine: Local empathetic fallback';
    }
  } catch (error) {
    engineStatus.textContent = 'AI Engine: status unavailable';
  }
}

function appendMessage(role, content) {
  const canonicalRole = role.includes('user') ? 'user' : 'assistant';
  history.push({ role: canonicalRole, content });

  const bubble = document.createElement('div');
  bubble.className = `bubble ${role}`;
  bubble.textContent = content;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

function renderActions(actions) {
  if (!actions.length) {
    chatActions.textContent = '';
    return;
  }

  chatActions.innerHTML = `<strong>Suggested next steps:</strong><br>${actions
    .map((item) => `- ${escapeHtml(item)}`)
    .join('<br>')}`;
}

function renderCheckin(data) {
  const planItems = (data.plan || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('');
  checkinResult.innerHTML = `
    <p><strong>Summary:</strong> ${escapeHtml(data.summary || '')}</p>
    <p><strong>Plan:</strong></p>
    <ul>${planItems}</ul>
    <p><strong>Affirmation:</strong> ${escapeHtml(data.affirmation || '')}</p>
  `;
}

function renderResources(resources) {
  if (!resources.length) {
    resourceList.innerHTML = '<p>No matching resources found.</p>';
    return;
  }

  resourceList.innerHTML = resources
    .map(
      (item) => `
      <article class="resource-item">
        <h3>${escapeHtml(item.name)}</h3>
        <p class="resource-meta"><strong>Contact:</strong> ${escapeHtml(item.contact)}</p>
        <p class="resource-meta"><strong>Mode:</strong> ${escapeHtml(item.mode)} | <strong>Cost:</strong> ${escapeHtml(item.cost)}</p>
        <p class="resource-meta"><strong>Coverage:</strong> ${escapeHtml(item.coverage)} | <strong>Hours:</strong> ${escapeHtml(item.hours)}</p>
        <p>${escapeHtml(item.notes)}</p>
      </article>
    `
    )
    .join('');
}

function toggleEmergency(show) {
  emergencyBanner.classList.toggle('hidden', !show);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

loadHealth();
loadResources();
