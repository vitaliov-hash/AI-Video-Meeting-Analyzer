if (window.APP_CONFIG?.mode === 'showcase') {
  const list = document.querySelector('#meeting-list');
  const details = document.querySelector('#details');
  const notice = document.querySelector('#notice');
  const t = window.I18N.t;
  const storageKey = 'meeting-analyzer-showcase-selected';
  const variantKey = 'meeting-analyzer-showcase-summary-version';
  let meetings = [];
  let selectedId = null;
  let summaryVariant = localStorage.getItem(variantKey) === 'reviewed' ? 'reviewed' : 'draft';
  document.documentElement.dataset.appMode = 'showcase';
  const esc = (value = '') => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const formatDate = value => new Intl.DateTimeFormat(window.I18N.locale,{dateStyle:'medium',timeStyle:'short'}).format(new Date(value));
  function renderList() {
    document.querySelector('#meeting-count').textContent = meetings.length;
    list.innerHTML = meetings.length ? meetings.map(m => `<button class="meeting ${m.id===selectedId?'selected':''}" data-id="${esc(m.id)}" aria-current="${m.id===selectedId}"><span class="meeting-title">${esc(m.filename)}</span><span class="meeting-meta"><span>${formatDate(m.added_at)}</span><span class="source-label">${t('demo')}</span><span class="status ready"><i class="dot"></i>${t('ready')}</span></span></button>`).join('') : `<p class="showcase-empty">${t('demoEmpty')}</p>`;
    list.querySelectorAll('.meeting').forEach(button => button.addEventListener('click', () => selectMeeting(button.dataset.id)));
  }
  function summaryMarkup(m) {
    const summary = m[summaryVariant];
    const cards = ['short_summary','decisions','next_tasks','open_questions'].map(key => `<article class="summary-card"><h3>${t(key)}</h3>${key==='short_summary'?`<p>${esc(summary[key])}</p>`:`<ul>${summary[key].map(item=>`<li>${esc(item)}</li>`).join('')}</ul>`}</article>`).join('');
    const reviewed = summaryVariant === 'reviewed';
    const notes = reviewed ? '' : `<aside class="editorial-notes"><strong>${t('editorialNotes')}</strong><ul>${m.editorial_notes.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></aside>`;
    return `<div class="summary-tabs" role="tablist" aria-label="${t('variantLabel')}"><button class="summary-tab" type="button" role="tab" data-variant="draft" aria-selected="${!reviewed}">${t('draftTab')}</button><button class="summary-tab" type="button" role="tab" data-variant="reviewed" aria-selected="${reviewed}">${t('reviewedTab')}</button></div><p class="summary-provenance">${t(reviewed?'reviewedProvenance':'draftProvenance')}</p><div class="summary-grid">${cards}</div>${notes}`;
  }
  function renderDetails(m) {
    details.innerHTML = `<div class="detail-head"><div><h2>${esc(m.filename)}</h2><p>${formatDate(m.added_at)} · ${t('demo')} · ${esc(m.language)}</p></div><span class="badge">${t('ready')}</span></div>${summaryMarkup(m)}<details class="transcript"><summary>${t('demoTranscript')} <span class="language">${esc(m.language)}</span></summary><p>${esc(m.transcript)}</p></details>`;
    details.querySelectorAll('.summary-tab').forEach(button => button.addEventListener('click', () => { summaryVariant=button.dataset.variant; localStorage.setItem(variantKey,summaryVariant); renderDetails(m); }));
  }
  function selectMeeting(id) {
    const m = meetings.find(item=>item.id===id);
    if (!m) return;
    selectedId=id; localStorage.setItem(storageKey,id); renderList(); renderDetails(m);
  }
  window.I18N.onChange(() => { renderList(); const m=meetings.find(item=>item.id===selectedId); if(m) renderDetails(m); });
  async function initialize() {
    try {
      const response=await fetch('/static/demo-data.json',{cache:'no-store'});
      if(!response.ok) throw new Error(t('demoLoadFailed'));
      const payload=await response.json();
      if(payload.mode!=='prepared-synthetic-showcase'||!Array.isArray(payload.meetings)) throw new Error(t('demoFormatFailed'));
      meetings=payload.meetings; renderList();
      const params=new URLSearchParams(window.location.search);
      const requested=params.get('meeting'); const saved=localStorage.getItem(storageKey);
      const variant=params.get('summary'); if(['draft','reviewed'].includes(variant)){summaryVariant=variant;localStorage.setItem(variantKey,variant);}
      selectMeeting(meetings.some(m=>m.id===requested)?requested:meetings.some(m=>m.id===saved)?saved:meetings[0]?.id);
    } catch(error) { notice.textContent=error.message||t('demoLoadFailed'); notice.hidden=false; list.innerHTML=`<p class="showcase-empty">${t('demoUnavailable')}</p>`; }
  }
  initialize();
}
