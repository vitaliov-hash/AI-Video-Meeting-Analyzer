if (window.APP_CONFIG?.mode === 'showcase') {
  const list = document.querySelector('#meeting-list');
  const details = document.querySelector('#details');
  const notice = document.querySelector('#notice');
  const storageKey = 'meeting-analyzer-showcase-selected';
  const variantKey = 'meeting-analyzer-showcase-summary-version';
  let meetings = [];
  let selectedId = null;
  let summaryVariant = localStorage.getItem(variantKey) === 'reviewed' ? 'reviewed' : 'draft';

  document.documentElement.dataset.appMode = 'showcase';

  const escapeHtml = (value = '') => String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
  const formatDate = value => new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(value));
  const titles = language => language === 'ru'
    ? { short_summary: 'Краткое содержание', decisions: 'Решения', next_tasks: 'Задачи', open_questions: 'Открытые вопросы' }
    : { short_summary: 'Summary', decisions: 'Decisions', next_tasks: 'Tasks', open_questions: 'Open questions' };

  function renderList() {
    document.querySelector('#meeting-count').textContent = meetings.length;
    list.innerHTML = meetings.map(meeting => `<button class="meeting ${meeting.id === selectedId ? 'selected' : ''}" data-id="${escapeHtml(meeting.id)}" aria-current="${meeting.id === selectedId ? 'true' : 'false'}"><span class="meeting-title">${escapeHtml(meeting.filename)}</span><span class="meeting-meta"><span>${formatDate(meeting.added_at)}</span><span class="source-label">${meeting.language === 'ru' ? 'Демо' : 'Demo'}</span><span class="status ready"><i class="dot"></i>Готово</span></span></button>`).join('');
    list.querySelectorAll('.meeting').forEach(button => button.addEventListener('click', () => selectMeeting(button.dataset.id)));
    if (!meetings.length) list.innerHTML = '<p class="showcase-empty">Подготовленные примеры не найдены.</p>';
  }

  function summaryMarkup(meeting) {
    const summary = meeting[summaryVariant];
    const sectionTitles = titles(meeting.language);
    const cards = Object.entries(sectionTitles).map(([key, title]) => {
      const value = summary[key];
      const content = key === 'short_summary'
        ? `<p>${escapeHtml(value)}</p>`
        : `<ul>${value.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
      return `<article class="summary-card"><h3>${title}</h3>${content}</article>`;
    }).join('');
    const reviewed = summaryVariant === 'reviewed';
    const provenance = reviewed
      ? 'Редакторская версия, сверенная только по вымышленной демонстрационной транскрипции.'
      : 'Первоначальный статический демонстрационный вариант. Это не ответ AI, полученный этим сайтом.';
    const notes = reviewed ? '' : `<aside class="editorial-notes"><strong>Что исправлено в редакторской версии</strong><ul>${meeting.editorial_notes.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></aside>`;
    return `<div class="summary-tabs" role="tablist" aria-label="Вариант конспекта"><button class="summary-tab" type="button" role="tab" data-variant="draft" aria-selected="${!reviewed}">Исходный пример</button><button class="summary-tab" type="button" role="tab" data-variant="reviewed" aria-selected="${reviewed}">Редакторская версия</button></div><p class="summary-provenance">${provenance}</p><div class="summary-grid">${cards}</div>${notes}`;
  }

  function renderDetails(meeting) {
    const language = meeting.language === 'ru' ? 'Русский' : 'English';
    details.innerHTML = `<div class="detail-head"><div><h2>${escapeHtml(meeting.filename)}</h2><p>${formatDate(meeting.added_at)} · ${escapeHtml(meeting.source)} · ${language}</p></div><span class="badge">Готово</span></div>${summaryMarkup(meeting)}<details class="transcript"><summary>Демонстрационная транскрипция <span class="language">${language}</span></summary><p>${escapeHtml(meeting.transcript)}</p></details>`;
    details.querySelectorAll('.summary-tab').forEach(button => button.addEventListener('click', () => {
      summaryVariant = button.dataset.variant;
      localStorage.setItem(variantKey, summaryVariant);
      renderDetails(meeting);
    }));
  }

  function selectMeeting(id) {
    const meeting = meetings.find(item => item.id === id);
    if (!meeting) return;
    selectedId = id;
    localStorage.setItem(storageKey, id);
    renderList();
    renderDetails(meeting);
  }

  async function initialize() {
    try {
      const response = await fetch('/static/demo-data.json', { cache: 'no-store' });
      if (!response.ok) throw new Error('Не удалось загрузить подготовленные примеры.');
      const payload = await response.json();
      if (payload.mode !== 'prepared-synthetic-showcase' || !Array.isArray(payload.meetings)) {
        throw new Error('Файл демонстрационных данных имеет неверный формат.');
      }
      meetings = payload.meetings;
      renderList();
      const params = new URLSearchParams(window.location.search);
      const requestedId = params.get('meeting');
      const savedId = localStorage.getItem(storageKey);
      const initialId = meetings.some(item => item.id === requestedId) ? requestedId : savedId;
      const requestedVariant = params.get('summary');
      if (requestedVariant === 'draft' || requestedVariant === 'reviewed') {
        summaryVariant = requestedVariant;
        localStorage.setItem(variantKey, summaryVariant);
      }
      selectMeeting(meetings.some(item => item.id === initialId) ? initialId : meetings[0]?.id);
    } catch (error) {
      notice.textContent = error.message || 'Не удалось загрузить демонстрационные примеры.';
      notice.hidden = false;
      list.innerHTML = '<p class="showcase-empty">История демонстраций временно недоступна.</p>';
    }
  }

  initialize();
}
