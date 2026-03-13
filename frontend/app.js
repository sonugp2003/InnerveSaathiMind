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

const bookingForm = document.getElementById('booking-form');
const bookingResult = document.getElementById('booking-result');
const bookingDateInput = document.getElementById('booking-date');
const bookingTimeInput = document.getElementById('booking-time');

const quickPrompts = document.getElementById('quick-prompts');

const history = [];
const API_BASE = (window.SAATHIMIND_API_BASE || '').replace(/\/+$/, '');
const IS_GITHUB_PAGES = window.location.hostname.endsWith('github.io');
let resourceCache = null;
const LOCAL_BOOKING_STORAGE_KEY = 'saathimind_bookings_v1';

const LOCAL_COUNSELLORS = [
  {
    name: 'Dr. Ananya Rao',
    languages: ['english', 'hindi', 'hinglish', 'multilingual'],
    modes: ['video', 'phone', 'chat'],
  },
  {
    name: 'Dr. Kabir Sharma',
    languages: ['english', 'hindi', 'multilingual'],
    modes: ['video', 'phone', 'in-person'],
  },
  {
    name: 'Dr. Meera Iyer',
    languages: ['english', 'hinglish'],
    modes: ['video', 'chat'],
  },
];

const HIGH_RISK_KEYWORDS = [
  'suicide',
  'sucide',
  'suside',
  'suiside',
  'suicde',
  'suicidal',
  'kill myself',
  'end my life',
  'ending everything',
  'harm myself',
  'self harm',
  'die',
  'marna hai',
  'jeene ka mann nahi',
  'khatam karna hai',
  'want to disappear forever',
];

const MEDIUM_RISK_KEYWORDS = [
  'hopeless',
  'worthless',
  'panic',
  'cant breathe',
  "can't breathe",
  'anxiety attack',
  'nobody understands',
  'alone',
  'empty',
  'burnout',
  'failure',
];

const STIGMA_KEYWORDS = [
  'log kya kahenge',
  'people will judge',
  'shame',
  'embarrassed',
  'weak if i ask',
  'family will not understand',
];

function apiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

function shouldTryRemoteApi() {
  // On GitHub Pages, same-origin /api routes do not exist unless an explicit API base is set.
  return Boolean(API_BASE) || !IS_GITHUB_PAGES;
}

async function fetchJson(path, options) {
  const response = await fetch(apiUrl(path), options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function normalizeText(value) {
  return String(value).toLowerCase().replace(/\s+/g, ' ').trim();
}

function findMatches(normalizedText, keywords) {
  return keywords.filter((keyword) => normalizedText.includes(keyword)).sort();
}

function containsHighRiskFuzzy(normalizedText) {
  // Catch common misspellings/variants of suicide intent phrases.
  return /\b(suicide|sucide|suside|suiside|suicde|suicidal|kill myself|end my life|harm myself|self harm)\b/.test(
    normalizedText
  );
}

function buildGuidance(riskLevel) {
  if (riskLevel === 'high') {
    return (
      'You deserve immediate human support right now. Please contact Tele-MANAS (14416) or ' +
      'Kiran (1800-599-0019), or call local emergency services if you are in immediate danger.'
    );
  }
  if (riskLevel === 'medium') {
    return (
      'Your message shows high emotional strain. Consider grounding steps, reaching out to a trusted ' +
      'person, and connecting with a counselor soon.'
    );
  }
  return 'No immediate crisis detected. Continue with supportive conversation and preventive care habits.';
}

function assessText(text) {
  const normalized = normalizeText(text);
  const highMatches = findMatches(normalized, HIGH_RISK_KEYWORDS);
  if (containsHighRiskFuzzy(normalized) && !highMatches.includes('suicide')) {
    highMatches.push('suicide');
  }
  const mediumMatches = findMatches(normalized, MEDIUM_RISK_KEYWORDS);
  const stigmaMatches = findMatches(normalized, STIGMA_KEYWORDS);

  let riskLevel = 'low';
  if (highMatches.length) {
    riskLevel = 'high';
  } else if (mediumMatches.length) {
    riskLevel = 'medium';
  }

  const triggers = [...new Set([...highMatches, ...mediumMatches, ...stigmaMatches])].sort();

  return {
    risk_level: riskLevel,
    triggers,
    immediate_help: riskLevel === 'high',
    guidance: buildGuidance(riskLevel),
  };
}

function buildSuggestedActions(riskLevel) {
  if (riskLevel === 'high') {
    return [
      'Call Tele-MANAS (14416) now.',
      'Call Kiran (1800-599-0019) now.',
      'Stay with a trusted person and seek immediate local help.',
    ];
  }
  if (riskLevel === 'medium') {
    return [
      'Pause and do 1 minute of slow breathing.',
      'Reach out to one trusted contact today.',
      'Consider speaking with a counselor this week.',
    ];
  }
  return [
    'Continue with a small actionable step.',
    'Track your mood with daily check-ins.',
    'Use peer or professional support early, not only in crisis.',
  ];
}

function generateLocalReply(message, language, riskLevel) {
  if (riskLevel === 'high') {
    return (
      'I am really glad you shared this. Your safety matters more than anything right now. ' +
      'Please contact Tele-MANAS at 14416 or Kiran at 1800-599-0019 immediately. ' +
      'If you feel in immediate danger, call emergency services and stay with a trusted person.'
    );
  }

  const msg = String(message).toLowerCase();
  let core;

  if (msg.includes('exam') || msg.includes('study') || msg.includes('marks')) {
    core =
      'It sounds like exam pressure is draining you, and that is very common among students. ' +
      'Try one 25-minute focused study sprint, then a 5-minute break. ' +
      'Write only 3 priority topics for today so your brain feels less overloaded.';
  } else if (msg.includes('alone') || msg.includes('lonely') || msg.includes('no one')) {
    core =
      'Feeling alone can feel very heavy, and sharing it here is a strong step. ' +
      "Can you reach out to one safe person with a simple message like, 'Can we talk for 10 mins?' " +
      'Also, do one grounding action right now: feet on floor, slow breathing for 1 minute.';
  } else if (msg.includes('family') || msg.includes('judge') || msg.includes('log kya')) {
    core =
      'Fear of judgement is real, especially when mental health is treated as taboo. ' +
      'Your struggle does not make you weak; it makes you human. ' +
      'Try sharing one small feeling instead of everything at once with someone you trust.';
  } else if (msg.includes('sleep') || msg.includes('tired') || msg.includes('burnout')) {
    core =
      'Your body and mind both sound exhausted. ' +
      'For tonight, aim for a digital sunset: stop scrolling 30 minutes before sleep. ' +
      'Do a brief brain-dump list so worries are parked outside your head.';
  } else {
    core =
      'Thank you for opening up. What you are feeling matters. ' +
      'Let us take this one step at a time: name the top emotion, rate it 0-10, and choose one tiny action for the next 15 minutes.';
  }

  const followUp =
    riskLevel === 'medium'
      ? 'What feels hardest right now: thoughts, body stress, or people pressure?'
      : 'Would you like a 2-minute grounding exercise or a practical plan for today?';

  if (language === 'hinglish') {
    return 'Main sun raha hoon, aur aap akela nahi ho. ' + core + ' Aapke liye yeh manageable ban sakta hai. ' + followUp;
  }

  return `${core} ${followUp}`;
}

function generateCheckinPlan(mood, stressors, note, language, safetyReport) {
  const riskLevel = String(safetyReport.risk_level || 'low');

  if (riskLevel === 'high') {
    return {
      summary: 'Your check-in suggests acute emotional distress.',
      plan: [
        'Call Tele-MANAS (14416) or Kiran (1800-599-0019) now.',
        'Move to a safe space and stay near a trusted person.',
        'Avoid being alone until the intensity comes down.',
      ],
      affirmation: 'Asking for urgent support is a strong and brave step.',
    };
  }

  const stressorText = stressors.length ? stressors.join(', ') : 'general stress';
  let summary;
  let plan;

  if (mood <= 3) {
    summary = `You seem to be having a very heavy day, especially around ${stressorText}.`;
    plan = [
      'Do a 60-second reset: inhale 4 sec, exhale 6 sec, repeat 8 rounds.',
      'Send one message to a trusted friend or mentor saying you need support.',
      'Pick one tiny task (5-10 min) and complete only that.',
    ];
  } else if (mood <= 6) {
    summary = `Your mood is in a vulnerable but manageable range, with stress around ${stressorText}.`;
    plan = [
      'Use a 25-minute focus sprint and keep phone away.',
      'Drink water and take a short walk before your next study block.',
      'Journal one worry and one action you can take today.',
    ];
  } else {
    summary = `You are currently doing reasonably okay despite pressure around ${stressorText}.`;
    plan = [
      'Keep momentum with 2 intentional breaks today.',
      'Check in with a friend who might be struggling too.',
      'Sleep hygiene: no doom-scrolling 30 minutes before bed.',
    ];
  }

  if (note) {
    summary += ' Thanks for sharing your note; your self-awareness is a protective strength.';
  }

  const affirmation =
    language === 'english'
      ? 'Your feelings are valid. Small consistent steps can create real emotional recovery.'
      : 'Jo aap feel kar rahe ho wo valid hai. Chhote steps bhi strong recovery banate hain.';

  return { summary, plan, affirmation };
}

async function getResourcesData() {
  if (Array.isArray(resourceCache)) {
    return resourceCache;
  }

  try {
    const response = await fetch('static/resources_india.json');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    resourceCache = await response.json();
    return resourceCache;
  } catch {
    resourceCache = [];
    return resourceCache;
  }
}

function searchResources(resources, query, mode, language) {
  const queryText = String(query || '').trim().toLowerCase();
  const modeText = String(mode || '').trim().toLowerCase();
  const languageText = String(language || '').trim().toLowerCase();

  return resources.filter((item) => {
    const searchableBlob = [item.name || '', item.notes || '', item.coverage || '', ...(item.tags || [])]
      .join(' ')
      .toLowerCase();

    if (queryText && !searchableBlob.includes(queryText)) {
      return false;
    }
    if (modeText && !String(item.mode || '').toLowerCase().includes(modeText)) {
      return false;
    }
    if (languageText && !String(item.language || '').toLowerCase().includes(languageText)) {
      return false;
    }
    return true;
  });
}

async function chatRequest(payload) {
  if (shouldTryRemoteApi()) {
    try {
      return await fetchJson('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      // Fall back to local mode when API is unavailable.
    }
  }

  const report = assessText(payload.message);
  return {
    reply: generateLocalReply(payload.message, payload.language, report.risk_level),
    safety_flags: report.triggers,
    suggested_actions: buildSuggestedActions(report.risk_level),
    escalate: Boolean(report.immediate_help),
  };
}

async function checkinRequest(payload) {
  if (shouldTryRemoteApi()) {
    try {
      return await fetchJson('/api/check-in', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      // Fall back to local mode when API is unavailable.
    }
  }

  const aggregateText = [...payload.stressors, payload.note || ''].join(' ');
  const report = assessText(aggregateText);
  const plan = generateCheckinPlan(payload.mood, payload.stressors, payload.note, payload.language, report);
  return {
    summary: plan.summary,
    plan: plan.plan,
    affirmation: plan.affirmation,
    escalate: Boolean(report.immediate_help),
  };
}

async function resourcesRequest(query, mode, language) {
  if (shouldTryRemoteApi()) {
    try {
      const params = new URLSearchParams();
      if (query) params.set('q', query);
      if (mode) params.set('mode', mode);
      if (language) params.set('language', language);
      const data = await fetchJson(`/api/resources?${params.toString()}`);
      return data.resources || [];
    } catch {
      // Fall back to local mode when API is unavailable.
    }
  }

  const resources = await getResourcesData();
  return searchResources(resources, query, mode, language);
}

async function healthRequest() {
  if (shouldTryRemoteApi()) {
    try {
      return await fetchJson('/api/health');
    } catch {
      // Fall back to local mode when API is unavailable.
    }
  }

  return {
    status: 'ok',
    engine: 'local',
    vertex_enabled: false,
    gemini_enabled: false,
    gemini_model: 'gemini-2.5-flash',
    vertex_model: 'local-browser-fallback',
    fallback_reason: 'Running without backend API.',
  };
}

function pickCounsellor(language, mode) {
  const exactMatch = LOCAL_COUNSELLORS.find((item) => item.languages.includes(language) && item.modes.includes(mode));
  if (exactMatch) {
    return exactMatch;
  }

  const modeMatch = LOCAL_COUNSELLORS.find((item) => item.modes.includes(mode));
  if (modeMatch) {
    return modeMatch;
  }

  return LOCAL_COUNSELLORS[0];
}

function createLocalBooking(payload) {
  const concernReport = assessText(payload.concern || '');
  const assigned = pickCounsellor(payload.language, payload.preferred_mode);
  const bookingId = `SM-${Date.now()}`;
  const urgentHelpRecommended = Boolean(concernReport.immediate_help);

  const result = {
    booking_id: bookingId,
    status: urgentHelpRecommended ? 'priority-support' : 'confirmed',
    assigned_counsellor: assigned.name,
    assigned_mode: payload.preferred_mode,
    scheduled_at: `${payload.preferred_date} ${payload.preferred_time}`,
    message: urgentHelpRecommended
      ? 'Your request is marked priority. Please contact Tele-MANAS (14416) or Kiran (1800-599-0019) now while support is arranged.'
      : `Your session request is booked with ${assigned.name}. You will receive a confirmation update shortly.`,
    urgent_help_recommended: urgentHelpRecommended,
    urgent_message: urgentHelpRecommended ? concernReport.guidance : null,
  };

  try {
    const raw = localStorage.getItem(LOCAL_BOOKING_STORAGE_KEY);
    const existing = raw ? JSON.parse(raw) : [];
    existing.push({
      ...payload,
      booking_id: bookingId,
      created_at: new Date().toISOString(),
    });
    localStorage.setItem(LOCAL_BOOKING_STORAGE_KEY, JSON.stringify(existing.slice(-30)));
  } catch {
    // If storage is blocked, still return success to keep booking UX smooth.
  }

  return result;
}

async function bookingRequest(payload) {
  if (shouldTryRemoteApi()) {
    try {
      return await fetchJson('/api/counsellor-booking', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      // Fall back to local booking mode when API is unavailable.
    }
  }

  return createLocalBooking(payload);
}

function initializeBookingDefaults() {
  if (!bookingDateInput || !bookingTimeInput) {
    return;
  }

  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  bookingDateInput.min = today;
  if (!bookingDateInput.value) {
    bookingDateInput.value = today;
  }

  const rounded = new Date(now.getTime() + 60 * 60 * 1000);
  rounded.setMinutes(0, 0, 0);
  const hh = String(rounded.getHours()).padStart(2, '0');
  const mm = String(rounded.getMinutes()).padStart(2, '0');
  if (!bookingTimeInput.value) {
    bookingTimeInput.value = `${hh}:${mm}`;
  }
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
  const pendingBubble = appendMessage('assistant pending', 'SaathiMind is reflecting...', false);

  try {
    const payload = {
      language: chatLanguage.value,
      message,
      history: history.slice(-6),
    };

    const data = await chatRequest(payload);
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
    const data = await checkinRequest({
      mood: Number(moodSlider.value),
      stressors,
      note,
      language: chatLanguage.value,
    });
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

if (bookingForm) {
  bookingForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const payload = {
      name: document.getElementById('booking-name').value.trim(),
      contact: document.getElementById('booking-contact').value.trim(),
      preferred_mode: document.getElementById('booking-mode').value,
      language: document.getElementById('booking-language').value,
      preferred_date: document.getElementById('booking-date').value,
      preferred_time: document.getElementById('booking-time').value,
      city: document.getElementById('booking-city').value.trim(),
      concern: document.getElementById('booking-concern').value.trim(),
    };

    if (!payload.name || !payload.contact || !payload.preferred_date || !payload.preferred_time) {
      bookingResult.innerHTML = '<p>Please fill name, contact, date, and time to continue.</p>';
      return;
    }

    bookingResult.innerHTML = '<p>Checking availability and matching counsellor...</p>';

    try {
      const booking = await bookingRequest(payload);
      renderBookingResult(booking);
      toggleEmergency(Boolean(booking.urgent_help_recommended));
      bookingForm.reset();
      initializeBookingDefaults();
    } catch {
      bookingResult.innerHTML = '<p>Could not complete booking right now. Please retry in a moment.</p>';
    }
  });
}

async function loadResources() {
  const query = document.getElementById('resource-query').value.trim();
  const mode = document.getElementById('resource-mode').value;
  const language = document.getElementById('resource-language').value;

  resourceList.innerHTML = '<p>Loading trusted resources...</p>';

  try {
    const resources = await resourcesRequest(query, mode, language);
    renderResources(resources);
  } catch (error) {
    resourceList.innerHTML = '<p>Could not load resources. Try again.</p>';
  }
}

async function loadHealth() {
  try {
    const data = await healthRequest();
    if (data.vertex_enabled) {
      engineStatus.textContent = `AI Engine: Vertex (${data.vertex_model})`;
    } else if (data.gemini_enabled) {
      engineStatus.textContent = `AI Engine: Gemini API (${data.gemini_model})`;
    } else if (shouldTryRemoteApi()) {
      engineStatus.textContent = 'AI Engine: Local empathetic fallback';
    } else {
      engineStatus.textContent = 'AI Engine: Browser fallback (no backend required)';
    }
  } catch (error) {
    engineStatus.textContent = 'AI Engine: status unavailable';
  }
}

function appendMessage(role, content, trackHistory = true) {
  if (trackHistory) {
    const canonicalRole = role.includes('user') ? 'user' : 'assistant';
    history.push({ role: canonicalRole, content });
  }

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

function renderBookingResult(booking) {
  const status = booking.status === 'priority-support' ? 'Priority support' : 'Confirmed';
  const urgentBlock = booking.urgent_message
    ? `<p><strong>Urgent guidance:</strong> ${escapeHtml(booking.urgent_message)}</p>`
    : '';

  bookingResult.innerHTML = `
    <p><strong>Status:</strong> ${escapeHtml(status)}</p>
    <p><strong>Booking ID:</strong> ${escapeHtml(booking.booking_id || '')}</p>
    <p><strong>Counsellor:</strong> ${escapeHtml(booking.assigned_counsellor || 'Assigned soon')}</p>
    <p><strong>Mode:</strong> ${escapeHtml(booking.assigned_mode || '')}</p>
    <p><strong>Scheduled:</strong> ${escapeHtml(booking.scheduled_at || '')}</p>
    <p><strong>Message:</strong> ${escapeHtml(booking.message || '')}</p>
    ${urgentBlock}
  `;
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
initializeBookingDefaults();
