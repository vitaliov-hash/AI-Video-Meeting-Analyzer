const list = document.querySelector('#meeting-list');
const details = document.querySelector('#details');
const notice = document.querySelector('#notice');
const input = document.querySelector('#video-file');
let meetings = [];
let selectedId = null;
const labels = {processing:'Обрабатывается',ready:'Готово',error:'Ошибка'};
const headings = {short_summary:'Краткое содержание',decisions:'Принятые решения',next_tasks:'Следующие задачи',open_questions:'Открытые вопросы'};

function esc(value='') { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function date(value) { return new Intl.DateTimeFormat('ru-RU',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)); }
function statusMarkup(status) { return `<span class="status ${status}"><i class="dot"></i>${labels[status]||'Ошибка'}</span>`; }

async function loadMeetings() {
  const response = await fetch('/api/meetings');
  if (!response.ok) throw new Error('Не удалось загрузить историю встреч.');
  meetings = await response.json();
  document.querySelector('#meeting-count').textContent = meetings.length;
  list.innerHTML = meetings.length ? meetings.map(m => `<button class="meeting ${m.id===selectedId?'selected':''}" data-id="${esc(m.id)}"><span class="meeting-title">${esc(m.filename)}</span><span class="meeting-meta"><span>${date(m.added_at)}</span>${statusMarkup(m.status)}</span></button>`).join('') : '<p class="empty-hint">Пока нет обработанных встреч.</p>';
  list.querySelectorAll('.meeting').forEach(button => button.addEventListener('click', () => selectMeeting(button.dataset.id)));
  const selected = meetings.find(m => m.id === selectedId);
  if (selected) renderDetails(selected);
}

async function selectMeeting(id) {
  selectedId = id;
  const response = await fetch(`/api/meetings/${encodeURIComponent(id)}`);
  if (!response.ok) { showNotice('Не удалось открыть эту встречу. Обновите список и попробуйте снова.'); return; }
  renderDetails(await response.json());
  await loadMeetings();
}

function renderDetails(m) {
  const badgeClass = m.status === 'error' ? 'error' : m.status === 'processing' ? 'processing' : '';
  let body = '';
  if (m.status === 'error') body = `<div class="error-box"><strong>Не удалось обработать запись.</strong><br>${esc(m.error||'Проверьте видео и настройки приложения.')}<br><label class="retry" for="video-file">Загрузить файл повторно</label></div>${m.transcript?`<details class="transcript"><summary>Расшифровка <span class="language">Язык: ${esc(m.language||'—')}</span></summary><p>${esc(m.transcript)}</p></details>`:''}`;
  else if (m.status === 'processing') body = '<p class="waiting">Распознавание речи и подготовка конспекта. Это может занять несколько минут.</p>';
  else body = `<div class="summary-grid">${Object.entries(headings).map(([key,title])=>`<article class="summary-card"><h3>${title}</h3>${key==='short_summary'?`<p>${esc(m.summary?.[key]||'')}</p>`:`<ul>${(m.summary?.[key]||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`}</article>`).join('')}</div><details class="transcript"><summary>Расшифровка <span class="language">Язык: ${esc(m.language||'—')}</span></summary><p>${esc(m.transcript||'')}</p></details>`;
  details.innerHTML = `<div class="detail-head"><div><h2>${esc(m.filename)}</h2><p>Добавлено ${date(m.added_at)}</p></div><span class="badge ${badgeClass}">${labels[m.status]||'Ошибка'}</span></div>${body}`;
}

function showNotice(message) { notice.textContent=message; notice.hidden=false; }
function hideNotice() { notice.hidden=true; }

input.addEventListener('change', async () => {
  const file=input.files?.[0]; if (!file) return;
  hideNotice();
  const ext=file.name.split('.').pop().toLowerCase();
  if (!['mp4','webm'].includes(ext)) { showNotice('Выберите видео в формате MP4 или WebM.'); input.value=''; return; }
  const form=new FormData(); form.append('file',file);
  try {
    const response=await fetch('/api/meetings',{method:'POST',body:form});
    const result=await response.json();
    if (!response.ok) throw new Error(result.detail||'Не удалось загрузить видео.');
    selectedId=result.id; await loadMeetings(); await selectMeeting(result.id);
  } catch(error) { showNotice(error.message||'Ошибка загрузки. Попробуйте снова.'); }
  finally { input.value=''; }
});

async function poll() {
  try { await loadMeetings(); }
  catch(error) { showNotice(error.message); }
  window.setTimeout(poll,2200);
}
poll();
