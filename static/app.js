const list = document.querySelector('#meeting-list');
const details = document.querySelector('#details');
const notice = document.querySelector('#notice');
const input = document.querySelector('#video-file');
const cloudForm = document.querySelector('#cloud-form');
const cloudUrl = document.querySelector('#cloud-url');
const cloudSubmit = document.querySelector('#cloud-submit');
const summaryLanguage = document.querySelector('#summary-language');
const t = window.I18N.t;
const teacherMode = window.APP_CONFIG?.mode === 'teacher-preview';
const teacherLoginForm = document.querySelector('#teacher-login');
const teacherPassword = document.querySelector('#teacher-password');
const teacherLoginSubmit = document.querySelector('#teacher-login-submit');
const teacherLoginError = document.querySelector('#teacher-login-error');
const teacherSession = document.querySelector('#teacher-session');
const teacherSessionStatus = document.querySelector('#teacher-session-status');
const teacherLogout = document.querySelector('#teacher-logout');
let meetings = [];
let selectedId = null;
let teacherToken = null;
const apiBaseUrl = String(window.APP_CONFIG?.apiBaseUrl || '').replace(/\/$/, '');
const apiUrl = path => `${apiBaseUrl}${path}`;
const headings = ['short_summary','decisions','next_tasks','open_questions'];

function esc(value='') { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function date(value) { return new Intl.DateTimeFormat(window.I18N.locale,{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)); }
function utcDate(value) { return new Intl.DateTimeFormat(window.I18N.locale,{dateStyle:'medium',timeStyle:'short',timeZone:'UTC'}).format(new Date(value)); }
function statusMarkup(status) { return `<span class="status ${status}"><i class="dot"></i>${t(status in {processing:1,ready:1,error:1}?status:'error')}</span>`; }
function errorText(message='') {
  if (/API_KEY|ключ AI|key/i.test(message)) return t('missingKey');
  if (/аудио|audio|ffmpeg/i.test(message)) return t('audioFailed');
  if (/AI-провайдер|JSON|структур/i.test(message)) return t('providerFailed');
  if (/прерван|interrupted/i.test(message)) return t('interrupted');
  return t('processingFailed');
}

function setTeacherAuthenticated(authenticated) {
  if (!teacherMode) return;
  document.documentElement.dataset.authenticated = authenticated ? 'true' : 'false';
  teacherLoginForm.hidden = authenticated;
  teacherSession.hidden = !authenticated;
  if (!authenticated) {
    teacherToken = null;
    meetings = [];
    selectedId = null;
    list.innerHTML = '';
    details.innerHTML = `<div class="empty"><h2>${t('loginRequired')}</h2></div>`;
  }
}

async function apiRequest(path, options={}) {
  const headers = new Headers(options.headers || {});
  if (teacherMode) {
    if (!teacherToken) throw new Error(t('loginPrompt'));
    headers.set('Authorization', `Bearer ${teacherToken}`);
  }
  const response = await fetch(apiUrl(path), {...options, headers});
  if (teacherMode && [401,410,503].includes(response.status)) {
    setTeacherAuthenticated(false);
    showNotice(t(response.status === 410 ? 'demoExpired' : response.status === 503 ? 'demoDisabled' : 'sessionExpired'));
  }
  return response;
}

async function refreshTeacherStatus() {
  const response = await apiRequest('/api/teacher-demo/status');
  const result = await response.json();
  if (!response.ok) throw new Error(t('sessionExpired'));
  teacherSessionStatus.textContent = `${t('remaining')}: ${result.analyses_remaining} / 2 · ${t('until')} ${utcDate(result.expires_at)} UTC`;
}

if (teacherMode) {
  teacherLoginForm.addEventListener('submit', async event => {
    event.preventDefault();
    teacherLoginError.hidden = true;
    teacherLoginSubmit.disabled = true;
    try {
      const response = await fetch(apiUrl('/api/teacher-demo/login'), {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({password:teacherPassword.value}),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(t('loginFailed'));
      teacherToken = result.access_token;
      teacherPassword.value = '';
      setTeacherAuthenticated(true);
      await refreshTeacherStatus();
      hideNotice();
      poll();
    } catch(error) {
      teacherToken = null;
      teacherLoginError.textContent = error.message || t('loginFailed');
      teacherLoginError.hidden = false;
      setTeacherAuthenticated(false);
    } finally {
      teacherLoginSubmit.disabled = false;
    }
  });
  teacherLogout.addEventListener('click', () => {
    setTeacherAuthenticated(false);
    hideNotice();
  });
}

async function loadMeetings() {
  const response = await apiRequest('/api/meetings');
  if (!response.ok) throw new Error(t('historyFailed'));
  meetings = await response.json();
  document.querySelector('#meeting-count').textContent = meetings.length;
  list.innerHTML = meetings.length ? meetings.map(m => `<button class="meeting ${m.id===selectedId?'selected':''}" data-id="${esc(m.id)}"><span class="meeting-title">${esc(m.filename)}</span><span class="meeting-meta"><span>${date(m.added_at)}</span><span class="source-label">${t(m.source==='cloud'?'cloudSource':'manualSource')}</span>${statusMarkup(m.status)}</span></button>`).join('') : `<p class="empty-hint">${t('noMeetings')}</p>`;
  list.querySelectorAll('.meeting').forEach(button => button.addEventListener('click', () => selectMeeting(button.dataset.id)));
  const selected = meetings.find(m => m.id === selectedId);
  if (selected) renderDetails(selected);
}

async function selectMeeting(id) {
  selectedId = id;
  const response = await apiRequest(`/api/meetings/${encodeURIComponent(id)}`);
  if (!response.ok) { showNotice(t('openFailed')); return; }
  renderDetails(await response.json());
  await loadMeetings();
}

function renderDetails(m) {
  const badgeClass = m.status === 'error' ? 'error' : m.status === 'processing' ? 'processing' : '';
  let body = '';
  if (m.status === 'error') body = `<div class="error-box"><strong>${errorText(m.error)}</strong><br><label class="retry" for="video-file">${t('retry')}</label></div>${m.transcript?`<details class="transcript"><summary>${t('transcript')} <span class="language">${t('speechLanguage')}: ${esc(m.language||'—')}</span></summary><p>${esc(m.transcript)}</p></details>`:''}`;
  else if (m.status === 'processing') body = `<p class="waiting">${t(m.phase||'processing')}… ${t('waiting')}</p>`;
  else body = `<div class="summary-grid">${headings.map(key=>`<article class="summary-card"><h3>${t(key)}</h3>${key==='short_summary'?`<p>${esc(m.summary?.[key]||'')}</p>`:`<ul>${(m.summary?.[key]||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`}</article>`).join('')}</div><p class="meeting-languages">${t('speechLanguage')}: ${esc(m.language||'—')} · ${t('briefLanguage')}: ${esc(m.summary_language||m.language||'—')}</p><details class="transcript"><summary>${t('transcript')} <span class="language">${t('speechLanguage')}: ${esc(m.language||'—')}</span></summary><p>${esc(m.transcript||'')}</p></details>`;
  details.innerHTML = `<div class="detail-head"><div><h2>${esc(m.filename)}</h2><p>${t('added')} ${date(m.added_at)} · ${t(m.source==='cloud'?'cloudSource':'manualSource')}${m.status==='processing'?` · ${t(m.phase||'processing')}`:''}</p></div><span class="badge ${badgeClass}">${t(m.status||'error')}</span></div>${body}`;
}

function showNotice(message) { notice.textContent=message; notice.hidden=false; }
function hideNotice() { notice.hidden=true; }

if (window.APP_CONFIG?.mode !== 'showcase') {
input.addEventListener('change', async () => {
  const file=input.files?.[0]; if (!file) return;
  hideNotice();
  const ext=file.name.split('.').pop().toLowerCase();
  if (!['mp4','webm'].includes(ext)) { showNotice(t('invalidVideo')); input.value=''; return; }
  const form=new FormData(); form.append('file',file); if(summaryLanguage.value) form.append('summary_language',summaryLanguage.value);
  try {
    const response=await apiRequest('/api/meetings',{method:'POST',body:form});
    const result=await response.json();
    if (!response.ok) throw new Error(t('uploadFailed'));
    selectedId=result.id; await loadMeetings(); await selectMeeting(result.id);
  } catch(error) { showNotice(error.message||t('uploadFailed')); }
  finally { input.value=''; }
});

cloudForm.addEventListener('submit', async event => {
  event.preventDefault();
  hideNotice(); cloudSubmit.disabled=true;
  cloudSubmit.textContent=t('adding');
  try {
    const response=await apiRequest('/api/meetings/cloud',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:cloudUrl.value.trim(),summary_language:summaryLanguage.value||null})});
    const result=await response.json();
    if (!response.ok) throw new Error(t('cloudFailed'));
    selectedId=result.id;
    if (result.duplicate) showNotice(t('duplicate'));
    cloudUrl.value=''; await loadMeetings(); await selectMeeting(result.id);
  } catch(error) { showNotice(error.message||t('cloudFailed')); }
  finally { cloudSubmit.disabled=false; cloudSubmit.textContent=t('addFromCloud'); }
});
}

async function poll() {
  if (teacherMode && !teacherToken) return;
  try { await loadMeetings(); }
  catch(error) { showNotice(error.message); }
  if (!teacherMode || teacherToken) window.setTimeout(poll,2200);
}
if (window.APP_CONFIG?.mode === 'showcase') {
  document.documentElement.dataset.appMode = 'showcase';
} else if (teacherMode) {
  document.documentElement.dataset.appMode = 'teacher-preview';
  setTeacherAuthenticated(false);
} else {
  poll();
}
window.I18N.onChange(() => {
  if (teacherMode && !teacherToken) { setTeacherAuthenticated(false); return; }
  if (window.APP_CONFIG?.mode !== 'showcase') { loadMeetings().catch(() => {}); }
});
