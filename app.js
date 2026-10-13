/* ================================================================
   Smart Wardrobe — frontend application logic
   Talks to the FastAPI backend in api.py. No fake data, no hardcoded
   outfit results — every screen is backed by a real endpoint.
   ================================================================ */

   const CONFIG = {
    apiBase: localStorage.getItem('wardrobe_api_base') || 'http://127.0.0.1:8000',
  };
  
  const OCCASIONS = ['casual', 'college', 'travel', 'office', 'formal', 'wedding', 'party', 'date', 'workout'];
  
  const TOKEN_KEY = 'wardrobe_auth_token';
  const USER_KEY = 'wardrobe_current_user';

  const state = {
    currentUser: null,
    usersList: [],
    wardrobe: [],
    stats: null,
    favorites: [],
    calendar: {},
    history: [],
    modelStatus: null,
    backendOnline: null,
    closet: { query: '', group: 'all', occasion: 'all', sort: 'recent' },
    stylist: { occasion: 'casual', temperature: 24, rain: false, outfits: [], activeIndex: 0 },
    calendarView: new Date(),
    pendingUpload: null, // { file, previewUrl, item, classification }
  };
  
  /* ----------------------------------------------------------------
     API HELPERS
     ---------------------------------------------------------------- */
  
  function resolveUrl(path) {
    if (!path) return '';
    if (/^https?:\/\//i.test(path)) return path;
    return CONFIG.apiBase.replace(/\/$/, '') + path;
  }
  
  async function apiRequest(method, path, { json, form } = {}) {
    const opts = { method, headers: {} };
    const token = localStorage.getItem(TOKEN_KEY) || (state.currentUser ? String(state.currentUser.id) : '1');
    if (token) {
      opts.headers['Authorization'] = `Bearer ${token}`;
    }
    if (json !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(json);
    } else if (form !== undefined) {
      opts.body = form;
    }
  
    let res;
    try {
      res = await fetch(resolveUrl(path), opts);
    } catch (err) {
      throw new ApiError(`Can't reach the backend at ${CONFIG.apiBase}. Is it running?`, 0, null);
    }
  
    let data = null;
    const text = await res.text();
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = text; }
    }
  
    if (!res.ok) {
      const detail = (data && data.detail) ? data.detail : (res.statusText || 'Request failed');
      throw new ApiError(detail, res.status, data);
    }
    return data;
  }
  
  class ApiError extends Error {
    constructor(message, status, data) {
      super(message);
      this.status = status;
      this.data = data;
    }
  }
  
  const api = {
    get: (path) => apiRequest('GET', path),
    post: (path, json) => apiRequest('POST', path, { json }),
    patch: (path, json) => apiRequest('PATCH', path, { json }),
    del: (path) => apiRequest('DELETE', path),
    upload: (path, form) => apiRequest('POST', path, { form }),
  };
  
  /* ----------------------------------------------------------------
     TOASTS
     ---------------------------------------------------------------- */
  
  function toast(message, type = 'default') {
    const stack = document.getElementById('toastStack');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => el.remove(), 3600);
  }
  
  /* ----------------------------------------------------------------
     NAVIGATION
     ---------------------------------------------------------------- */
  
  function goto(roomName) {
    document.querySelectorAll('.room').forEach((r) => r.classList.remove('active'));
    document.querySelectorAll('.masthead-nav button').forEach((b) => b.classList.remove('active'));
    const room = document.getElementById(`room-${roomName}`);
    const navBtn = document.querySelector(`.masthead-nav button[data-room="${roomName}"]`);
    if (room) room.classList.add('active');
    if (navBtn) navBtn.classList.add('active');
    window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
  
    if (roomName === 'home') refreshDashboard();
    if (roomName === 'closet') refreshCloset();
    if (roomName === 'stylist') refreshStylistBanner();
    if (roomName === 'calendar') refreshCalendar();
    if (roomName === 'favorites') refreshFavorites();
    if (roomName === 'history') refreshHistory();
  }
  
  document.querySelectorAll('.masthead-nav button[data-room]').forEach((btn) => {
    btn.addEventListener('click', () => goto(btn.dataset.room));
  });
  document.querySelectorAll('[data-goto]').forEach((el) => {
    el.addEventListener('click', () => goto(el.dataset.goto));
  });
  
  /* ----------------------------------------------------------------
     BACKEND HEALTH CHECK
     ---------------------------------------------------------------- */
  
  async function checkHealth() {
    try {
      const status = await api.get('/api/status');
      state.backendOnline = true;
      state.modelStatus = status.model_status;
    } catch (err) {
      state.backendOnline = false;
      state.modelStatus = null;
    }
    renderHomeBanner();
    renderStylistBanner();
  }
  
  /* ----------------------------------------------------------------
     BANNERS (reused shape across rooms)
     ---------------------------------------------------------------- */
  
  function offlineBannerHtml() {
    return `<div class="banner">
      <strong>Can't reach the backend</strong>
      The app is looking for the API at <code>${CONFIG.apiBase}</code>. Start it with
      <code>uvicorn fastApi:app --reload</code>, or click the status pill above to change the address.
      <div><button class="retry" onclick="checkHealth().then(()=>location.reload())">Retry</button></div>
    </div>`;
  }
  
  function aiUnavailableBannerHtml() {
    const errors = (state.modelStatus && state.modelStatus.errors) || [];
    return `<div class="banner warn">
      <strong>Gemini AI isn't available</strong>
      Outfit generation is temporarily unavailable. The closet, calendar, favorites, and history still work normally.
      ${errors.length ? `<ul>${errors.map((e) => `<li>${escapeHtml(String(e))}</li>`).join('')}</ul>` : ''}
    </div>`;
  }
  
  function renderHomeBanner() {
    const el = document.getElementById('homeBanner');
    if (!el) return;
    el.innerHTML = state.backendOnline === false ? offlineBannerHtml() : '';
  }
  
  function renderStylistBanner() {
    const el = document.getElementById('stylistBanner');
    if (!el) return;
    const mode = state.modelStatus && state.modelStatus.ranking_mode;
    if (state.backendOnline === false) {
      el.innerHTML = offlineBannerHtml();
    } else if (mode === 'unavailable') {
      el.innerHTML = aiUnavailableBannerHtml();
    } else {
      el.innerHTML = '';
    }
  }
  function refreshStylistBanner() { checkHealth(); }
  
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
  
  /* ----------------------------------------------------------------
     DASHBOARD (HOME)
     ---------------------------------------------------------------- */
  
  async function refreshDashboard() {
    await checkHealth();
    renderUserBar();
    const grid = document.getElementById('statGrid');
    try {
      const stats = await api.get('/api/wardrobe/stats');
      state.stats = stats;
  
      grid.innerHTML = `
        <div class="stat-card"><div class="num">${stats.total ?? 0}</div><div class="label tracked">pieces in closet</div></div>
        <div class="stat-card"><div class="num">${stats.favorites_count ?? 0}</div><div class="label tracked">saved looks</div></div>
        <div class="stat-card"><div class="num">${stats.planned_outfits ?? 0}</div><div class="label tracked">planned outfits</div></div>
        <div class="stat-card"><div class="num">${stats.worn_outfits ?? 0}</div><div class="label tracked">outfits worn</div></div>
      `;
  
      const recentGrid = document.getElementById('recentGrid');
      const recent = stats.recent_items || [];
      if (!recent.length) {
        recentGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;">
          <span class="serif">The closet is empty</span>
          Add your first piece to get started.
          <div><button class="btn btn-primary" data-goto="add">+ Add Item</button></div>
        </div>`;
        recentGrid.querySelector('[data-goto]').addEventListener('click', () => goto('add'));
      } else {
        recentGrid.innerHTML = recent.map((item) => garmentCardHtml(item, { newBadge: true })).join('');
        attachGarmentClickHandlers(recentGrid, recent);
      }
  
      const breakdown = document.getElementById('breakdownList');
      const byGroup = {
        top: stats.tops || 0,
        bottom: stats.bottoms || 0,
        outerwear: stats.outerwear || 0,
        "one-piece": stats.one_piece || 0,
      };
      const groups = Object.entries(byGroup).sort((a, b) => b[1] - a[1]);
      const max = Math.max(1, ...groups.map((g) => g[1]));
      if (!groups.length) {
        breakdown.innerHTML = '';
      } else {
        breakdown.innerHTML = groups.map(([group, count]) => `
          <div class="breakdown-row">
            <div class="bd-label" style="text-transform:capitalize;">${group}</div>
            <div class="bd-bar-wrap"><div class="bd-bar" style="width:${(count / max) * 100}%"></div></div>
            <div class="bd-count">${count}</div>
          </div>
        `).join('');
      }
    } catch (err) {
      grid.innerHTML = `<div style="grid-column:1/-1;padding:20px;color:var(--charcoal-soft);font-size:12px;">Stats unavailable — ${escapeHtml(err.message)}</div>`;
    }
  }
  
  /* ----------------------------------------------------------------
     SHARED: garment card + wardrobe loading
     ---------------------------------------------------------------- */
  
  function garmentCardHtml(item, { index, newBadge } = {}) {
    const isNew = newBadge && item.added_at && (Date.now() - new Date(item.added_at).getTime() < 1000 * 60 * 60 * 24 * 3);
    const primaryOcc = (item.occasions && item.occasions[0]) || (item.tags && item.tags[0]) || '';
    return `
      <div class="garment" data-id="${escapeHtml(item.id)}">
        <div class="thumb-wrap">
          <img src="${resolveUrl(item.url)}" alt="${escapeHtml(item.name)}" loading="lazy" />
          ${index !== undefined ? `<span class="overlay-index">${String(index + 1).padStart(2, '0')}</span>` : ''}
          ${isNew ? '<span class="overlay-new">NEW</span>' : ''}
        </div>
        <div class="caption">
          <span class="gname">${escapeHtml(item.name)}</span>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
            <span class="group tracked">${escapeHtml(item.group)}</span>
            ${primaryOcc ? `<span class="occ-badge">${escapeHtml(primaryOcc)}</span>` : ''}
          </div>
        </div>
      </div>`;
  }
  
  function attachGarmentClickHandlers(container, items) {
    container.querySelectorAll('.garment').forEach((el) => {
      el.addEventListener('click', () => {
        const item = items.find((i) => i.id === el.dataset.id);
        if (item) openItemModal(item);
      });
    });
  }
  
  async function loadWardrobe(force) {
    if (state.wardrobe.length && !force) return state.wardrobe;
    const data = await api.get('/api/wardrobe');
    state.wardrobe = data.items;
    return state.wardrobe;
  }
  
  /* ----------------------------------------------------------------
     CLOSET
     ---------------------------------------------------------------- */
  
  async function refreshCloset() {
    const grid = document.getElementById('rackGrid');
    const banner = document.getElementById('closetBanner');
    grid.innerHTML = Array.from({ length: 10 }).map(() => '<div class="garment skeleton-card skeleton"></div>').join('');
    try {
      await loadWardrobe(true);
      banner.innerHTML = state.backendOnline === false ? offlineBannerHtml() : '';
      renderCloset();
    } catch (err) {
      banner.innerHTML = offlineBannerHtml();
      grid.innerHTML = '';
    }
  }
  
  function renderCloset() {
    const { query, group, sort, occasion } = state.closet;
    let items = [...state.wardrobe];
  
    if (group !== 'all') items = items.filter((i) => i.group === group);
    if (occasion && occasion !== 'all') {
      const occ = occasion.toLowerCase();
      items = items.filter((i) =>
        (i.occasions && i.occasions.map((o) => o.toLowerCase()).includes(occ)) ||
        (i.tags && i.tags.map((t) => t.toLowerCase()).includes(occ))
      );
    }
    if (query) {
      const q = query.toLowerCase();
      items = items.filter((i) =>
        i.name.toLowerCase().includes(q) ||
        i.category.toLowerCase().includes(q) ||
        (i.tags && i.tags.some((t) => t.toLowerCase().includes(q))) ||
        (i.occasions && i.occasions.some((o) => o.toLowerCase().includes(q)))
      );
    }
  
    if (sort === 'name') items.sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === 'category') items.sort((a, b) => a.group.localeCompare(b.group) || a.name.localeCompare(b.name));
    else items.sort((a, b) => (b.added_at || '').localeCompare(a.added_at || ''));
  
    const grid = document.getElementById('rackGrid');
    if (!items.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;">
        <span class="serif">Nothing here</span>
        ${state.wardrobe.length ? `No pieces found for "${escapeHtml(occasion !== 'all' ? occasion : (group !== 'all' ? group : 'this filter'))}". Try selecting "All" or a different occasion.` : 'Your closet is empty — add your first piece.'}
        ${state.wardrobe.length ? '' : '<div><button class="btn btn-primary" data-goto="add">+ Add Item</button></div>'}
      </div>`;
      const addBtn = grid.querySelector('[data-goto]');
      if (addBtn) addBtn.addEventListener('click', () => goto('add'));
      return;
    }
  
    grid.innerHTML = items.map((item, idx) => garmentCardHtml(item, { index: idx })).join('');
    attachGarmentClickHandlers(grid, items);
  }
  
  document.getElementById('closetSearch').addEventListener('input', (e) => {
    state.closet.query = e.target.value;
    renderCloset();
  });
  document.getElementById('closetFilters').addEventListener('click', (e) => {
    const btn = e.target.closest('.chip');
    if (!btn) return;
    document.querySelectorAll('#closetFilters .chip').forEach((c) => c.classList.remove('active'));
    btn.classList.add('active');
    state.closet.group = btn.dataset.group;
    renderCloset();
  });

  const occFilterBar = document.getElementById('closetOccasionFilter');
  if (occFilterBar) {
    occFilterBar.addEventListener('click', (e) => {
      const btn = e.target.closest('.occasion-chip');
      if (!btn) return;
      occFilterBar.querySelectorAll('.occasion-chip').forEach((c) => c.classList.remove('selected'));
      btn.classList.add('selected');
      state.closet.occasion = btn.dataset.occ;
      renderCloset();
    });
  }

  document.getElementById('closetSort').addEventListener('change', (e) => {
    state.closet.sort = e.target.value;
    renderCloset();
  });
  
  /* ----------------------------------------------------------------
     ITEM DETAIL MODAL (edit / delete)
     ---------------------------------------------------------------- */
  
  function openItemModal(item) {
    const title = document.getElementById('modalTitle');
    const sub = document.getElementById('modalSub');
    const body = document.getElementById('modalBody');
    const actions = document.getElementById('modalActions');
  
    title.textContent = item.name;
    sub.textContent = `${item.category} Â· ${item.group}`;
  
    let currentTags = [...item.tags];
  
    body.innerHTML = `
      <img class="item-detail-img" src="${resolveUrl(item.url)}" alt="${escapeHtml(item.name)}" />
      <div class="detail-meta">
        Added <b>${item.added_at ? new Date(item.added_at).toLocaleDateString() : 'unknown date'}</b>
        ${item.confidence ? ` Â· AI confidence <b>${Math.round(item.confidence * 100)}%</b>` : ''}
        ${item.source === 'uploaded' ? ' Â· uploaded' : ' Â· seed item'}
      </div>
      <div class="form-row">
        <label>Name</label>
        <input type="text" id="editName" value="${escapeHtml(item.name)}" />
      </div>
      <div class="form-row">
        <label>Category</label>
        <input type="text" id="editCategory" value="${escapeHtml(item.category)}" />
      </div>
      <div class="form-row">
        <label>Tags</label>
        <div class="tag-editor" id="editTags"></div>
        <div class="tag-input-row">
          <input type="text" id="newTagInput" placeholder="Add a tag and press Enter" />
        </div>
      </div>
    `;
  
    function renderTags() {
      const wrap = body.querySelector('#editTags');
      wrap.innerHTML = currentTags.map((t, i) => `
        <span class="tag-chip">${escapeHtml(t)}<button data-i="${i}">&times;</button></span>
      `).join('') || '<span style="font-size:11px;color:var(--charcoal-soft);">No tags yet</span>';
      wrap.querySelectorAll('button').forEach((b) => {
        b.addEventListener('click', () => {
          currentTags.splice(Number(b.dataset.i), 1);
          renderTags();
        });
      });
    }
    renderTags();
  
    body.querySelector('#newTagInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.value.trim()) {
        currentTags.push(e.target.value.trim());
        e.target.value = '';
        renderTags();
      }
    });
  
    actions.innerHTML = `
      <button class="text-btn danger" id="deleteItemBtn">Delete item</button>
      <button class="btn btn-primary" id="saveItemBtn">Save changes</button>
    `;
  
    actions.querySelector('#saveItemBtn').addEventListener('click', async () => {
      const name = body.querySelector('#editName').value.trim() || item.name;
      const category = body.querySelector('#editCategory').value.trim() || item.category;
      try {
        await api.patch(`/api/wardrobe/items/${encodeURIComponent(item.id)}`, { name, category, tags: currentTags });
        toast('Item updated', 'success');
        closeModal();
        await loadWardrobe(true);
        renderCloset();
        refreshDashboard();
      } catch (err) {
        toast(`Couldn't save: ${err.message}`, 'error');
      }
    });
  
    actions.querySelector('#deleteItemBtn').addEventListener('click', async () => {
      if (!confirm(`Remove "${item.name}" from your closet? This can't be undone.`)) return;
      try {
        await api.del(`/api/wardrobe/items/${encodeURIComponent(item.id)}`);
        toast('Item deleted', 'success');
        closeModal();
        await loadWardrobe(true);
        renderCloset();
        refreshDashboard();
      } catch (err) {
        toast(`Couldn't delete: ${err.message}`, 'error');
      }
    });
  
    openModal();
  }
  
  /* ----------------------------------------------------------------
     MODAL PLUMBING
     ---------------------------------------------------------------- */
  
  const modalOverlay = document.getElementById('modalOverlay');
  function openModal() { modalOverlay.classList.add('open'); }
  function closeModal() { modalOverlay.classList.remove('open'); }
  document.getElementById('modalClose').addEventListener('click', closeModal);
  modalOverlay.addEventListener('click', (e) => { if (e.target === modalOverlay) closeModal(); });
  
  /* ----------------------------------------------------------------
     ADD ITEM
     ---------------------------------------------------------------- */
  
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const dzPreview = document.getElementById('dzPreview');
  const dzIcon = document.getElementById('dzIcon');
  const dzTitle = document.getElementById('dzTitle');
  const dzSub = document.getElementById('dzSub');
  
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) handleUpload(fileInput.files[0]);
  });
  ['dragover', 'dragenter'].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add('drag-over'); })
  );
  ['dragleave', 'drop'].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove('drag-over'); })
  );
  dropzone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  });
  
  async function handleUpload(file) {
    if (!file.type.startsWith('image/')) {
      toast('Please choose an image file', 'error');
      return;
    }
  
    const previewUrl = URL.createObjectURL(file);
    dzPreview.src = previewUrl;
    dzPreview.style.display = 'block';
    dzIcon.style.display = 'none';
    dzTitle.style.display = 'none';
    dzSub.style.display = 'none';
    dropzone.classList.add('analyzing');
  
    document.getElementById('addBanner').innerHTML = '';
  
    const form = new FormData();
    form.append('file', file);
  
    try {
      const result = await api.upload('/api/wardrobe/items', form);
      state.pendingUpload = { file, previewUrl, item: result.item, classification: result.classification };
      if (result.warning) {
        document.getElementById('addBanner').innerHTML = `<div class="banner warn"><strong>Saved without full AI tagging</strong>${escapeHtml(result.warning)}</div>`;
      }
      renderClassifyPanel();
      toast('Photo saved to your closet', 'success');
    } catch (err) {
      document.getElementById('addBanner').innerHTML = `<div class="banner"><strong>Upload failed</strong>${escapeHtml(err.message)}</div>`;
      resetDropzone();
    } finally {
      dropzone.classList.remove('analyzing');
    }
  }
  
  function resetDropzone() {
    dzPreview.style.display = 'none';
    dzIcon.style.display = 'block';
    dzTitle.style.display = 'block';
    dzSub.style.display = 'block';
    fileInput.value = '';
  }
  
  function renderClassifyPanel() {
    const panel = document.getElementById('classifyPanel');
    const { item, classification } = state.pendingUpload;
  
    const attrs = [];
    if (classification && classification.attributes) {
      Object.entries(classification.attributes).forEach(([group, values]) => {
        (values || []).slice(0, 2).forEach((v) => attrs.push(`${group}: ${v.name}`));
      });
    }
  
    panel.innerHTML = `
      <div class="predicted-row">
        <span class="pred-cat">${escapeHtml(item.category)}</span>
        ${item.confidence ? `<span class="pred-conf">${Math.round(item.confidence * 100)}% confident</span>` : '<span class="pred-conf">manual</span>'}
      </div>
      ${attrs.length ? `<div class="attr-list">${attrs.map((a) => `<span class="attr-pill">${escapeHtml(a)}</span>`).join('')}</div>` : ''}
  
      <div class="form-row">
        <label>Name</label>
        <input type="text" id="upName" value="${escapeHtml(item.name)}" />
      </div>
      <div class="form-row">
        <label>Category</label>
        <input type="text" id="upCategory" value="${escapeHtml(item.category)}" />
      </div>
      <div class="form-row">
        <label>Tags</label>
        <div class="tag-editor" id="upTags"></div>
        <div class="tag-input-row"><input type="text" id="upNewTag" placeholder="Add a tag and press Enter" /></div>
      </div>
      <div class="add-actions">
        <button class="btn btn-ghost" id="discardBtn">Discard</button>
        <button class="btn btn-primary" id="confirmBtn">Add to Closet</button>
      </div>
    `;
  
    let tags = [...item.tags];
    function renderTags() {
      const wrap = panel.querySelector('#upTags');
      wrap.innerHTML = tags.map((t, i) => `<span class="tag-chip">${escapeHtml(t)}<button data-i="${i}">&times;</button></span>`).join('')
        || '<span style="font-size:11px;color:var(--charcoal-soft);">No tags yet — add a few to help outfit matching.</span>';
      wrap.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { tags.splice(Number(b.dataset.i), 1); renderTags(); }));
    }
    renderTags();
    panel.querySelector('#upNewTag').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.value.trim()) { tags.push(e.target.value.trim()); e.target.value = ''; renderTags(); }
    });
  
    panel.querySelector('#discardBtn').addEventListener('click', async () => {
      try {
        await api.del(`/api/wardrobe/items/${encodeURIComponent(item.id)}`);
      } catch (_) { /* best effort */ }
      state.pendingUpload = null;
      resetDropzone();
      panel.innerHTML = `<div class="classify-empty"><span class="serif">Discarded</span>Upload another photo whenever you're ready.</div>`;
    });
  
    panel.querySelector('#confirmBtn').addEventListener('click', async () => {
      const name = panel.querySelector('#upName').value.trim() || item.name;
      const category = panel.querySelector('#upCategory').value.trim() || item.category;
      try {
        await api.patch(`/api/wardrobe/items/${encodeURIComponent(item.id)}`, { name, category, tags });
        toast('Added to your closet', 'success');
        state.pendingUpload = null;
        resetDropzone();
        panel.innerHTML = `<div class="classify-empty"><span class="serif">All set</span>"${escapeHtml(name)}" is in your closet.</div>`;
        await loadWardrobe(true);
        goto('closet');
      } catch (err) {
        toast(`Couldn't save: ${err.message}`, 'error');
      }
    });
  }
  
  /* ----------------------------------------------------------------
     AI STYLIST
     ---------------------------------------------------------------- */
  
  let stylistRequestSeq = 0;
  const occasionGrid = document.getElementById('occasionGrid');
  occasionGrid.innerHTML = OCCASIONS.map((o) => `<button class="occasion-chip ${o === state.stylist.occasion ? 'selected' : ''}" data-occasion="${o}">${o}</button>`).join('');
  occasionGrid.addEventListener('click', (e) => {
    const btn = e.target.closest('.occasion-chip');
    if (!btn) return;
    state.stylist.occasion = btn.dataset.occasion;
    occasionGrid.querySelectorAll('.occasion-chip').forEach((c) => c.classList.remove('selected'));
    btn.classList.add('selected');
    generateOutfits();
  });
  
  const tempRange = document.getElementById('tempRange');
  const tempValue = document.getElementById('tempValue');
  tempRange.addEventListener('input', () => {
    state.stylist.temperature = Number(tempRange.value);
    tempValue.textContent = tempRange.value;
  });
  
  document.getElementById('rainToggle').addEventListener('change', (e) => {
    state.stylist.rain = e.target.checked;
  });
  
  document.getElementById('useWeatherBtn').addEventListener('click', async () => {
    const btn = document.getElementById('useWeatherBtn');
    const original = btn.textContent;
    btn.textContent = 'Locating…';
    try {
      const pos = await new Promise((resolve, reject) => {
        if (!navigator.geolocation) return reject(new Error('Geolocation not supported'));
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000 });
      });
      const { latitude, longitude } = pos.coords;
      btn.textContent = 'Fetching weather…';
      const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,precipitation`);
      const data = await res.json();
      const temp = Math.round(data.current.temperature_2m);
      const rain = data.current.precipitation > 0;
      tempRange.value = Math.max(-10, Math.min(45, temp));
      tempValue.textContent = tempRange.value;
      state.stylist.temperature = Number(tempRange.value);
      state.stylist.rain = rain;
      document.getElementById('rainToggle').checked = rain;
      toast(`Using live weather: ${temp}Â°C${rain ? ', rain detected' : ''}`, 'success');
    } catch (err) {
      toast("Couldn't get your location/weather — set it manually.", 'error');
    } finally {
      btn.textContent = original;
    }
  });
  
  const generateBtn = document.getElementById('generateBtn');
  generateBtn.addEventListener('click', generateOutfits);
  
  async function generateOutfits() {
    const seq = ++stylistRequestSeq;
    const resultsCol = document.getElementById('resultsCol');
    generateBtn.disabled = true;
    generateBtn.textContent = 'Composing look…';
    resultsCol.innerHTML = `
      <div class="featured-card"><div class="featured-body">
        <div class="skeleton" style="height:220px;margin-bottom:18px;"></div>
        <div class="skeleton" style="height:14px;width:70%;margin-bottom:10px;"></div>
        <div class="skeleton" style="height:14px;width:40%;"></div>
      </div></div>`;
  
    try {
      const payload = {
        occasion: state.stylist.occasion,
        temperature_c: state.stylist.temperature,
        rain: state.stylist.rain,
      };
      const data = await api.post('/api/outfits/generate', payload);

      if (seq !== stylistRequestSeq) return;
  
      if (data.error) {
        resultsCol.innerHTML = `<div class="banner"><strong>Couldn't build a look</strong>${escapeHtml(data.error)}
          ${data.details && data.details.length ? `<ul>${data.details.map((d) => `<li>${escapeHtml(String(d))}</li>`).join('')}</ul>` : ''}</div>`;
        state.stylist.outfits = [];
        return;
      }
  
      if (!data.outfits.length) {
        resultsCol.innerHTML = `<div class="empty-state">
          <span class="serif">No matching outfits</span>
          Nothing in your closet fits "${escapeHtml(state.stylist.occasion)}" at ${state.stylist.temperature}Â°C. Try a different occasion or add more pieces.
        </div>`;
        state.stylist.outfits = [];
        return;
      }
  
      state.stylist.outfits = data.outfits;
      state.stylist.activeIndex = 0;
      renderStylistResults();
    } catch (err) {
      if (seq !== stylistRequestSeq) return;
      resultsCol.innerHTML = `<div class="banner"><strong>Something went wrong</strong>${escapeHtml(err.message)}</div>`;
    } finally {
      if (seq === stylistRequestSeq) {
        generateBtn.disabled = false;
        generateBtn.textContent = 'Build the look';
      }
    }
  }
  
  function renderStylistResults() {
    const resultsCol = document.getElementById('resultsCol');
    const outfits = state.stylist.outfits;
    const idx = state.stylist.activeIndex;
    const outfit = outfits[idx];
  
    const pct = Math.round((outfit.compatibility_score || 0) * 100);
  
    resultsCol.innerHTML = `
      <div class="featured-card">
        <div class="featured-head">
          <span class="look-tag tracked">Look ${idx + 1} of ${outfits.length} Â· ${escapeHtml(state.stylist.occasion)}</span>
          <div class="score-ring"><span class="score-num">${pct}%</span></div>
        </div>
        <div class="featured-body">
          <div class="featured-imgs">
            ${outfit.items.map((it) => `
              <div class="piece">
                <img src="${resolveUrl(it.url)}" alt="${escapeHtml(it.name || it.category || 'garment')}" />
                <div class="piece-name">${escapeHtml(it.name || '')}</div>
                <div class="piece-cat">${escapeHtml(it.category || '')}</div>
              </div>`).join('')}
          </div>
          <div class="explanation">"${escapeHtml(outfit.explanation || 'A balanced pick for the occasion.')}"</div>
          <div class="score-breakdown">
            ${scoreItem('Occasion', outfit.occasion_score)}
            ${scoreItem('Weather', outfit.weather_score)}
            ${scoreItem('Style match', outfit.vit_score)}
            ${scoreItem('Coverage', outfit.garment_compatibility_score)}
          </div>
          <div class="featured-actions">
            <button class="btn btn-primary" id="saveFavBtn">Save to Favorites</button>
            <button class="btn btn-ghost" id="tryAnotherBtn" ${outfits.length < 2 ? 'disabled' : ''}>Try another</button>
            <button class="text-btn" id="planDateToggle">Plan for a date</button>
          </div>
          <div class="date-inline" id="dateInline">
            <input type="date" id="planDateInput" min="${todayIso()}" value="${todayIso()}" />
            <button class="btn btn-primary" id="confirmPlanBtn">Add to calendar</button>
          </div>
        </div>
        ${outfits.length > 1 ? `
          <div class="featured-body" style="border-top:1px solid var(--stone);">
            <div class="other-looks-head tracked">Other looks from this closet</div>
            <div class="other-looks-rail">
              ${outfits.map((o, i) => `
                <button class="other-look-thumb ${i === idx ? 'active' : ''}" data-idx="${i}">
                  <span class="oth-rank">${i + 1}</span>
                  ${o.items.slice(0, 2).map((it) => `<img src="${resolveUrl(it.url)}" />`).join('')}
                </button>`).join('')}
            </div>
          </div>` : ''}
      </div>
    `;
  
    function scoreItem(label, val) {
      if (val === null || val === undefined) return '';
      return `<div class="sb-item"><b>${Math.round(val * 100)}%</b>${label}</div>`;
    }
  
    resultsCol.querySelector('#tryAnotherBtn')?.addEventListener('click', () => {
      state.stylist.activeIndex = (state.stylist.activeIndex + 1) % outfits.length;
      renderStylistResults();
    });
  
    resultsCol.querySelectorAll('.other-look-thumb').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.stylist.activeIndex = Number(btn.dataset.idx);
        renderStylistResults();
      });
    });
  
    resultsCol.querySelector('#saveFavBtn').addEventListener('click', async () => {
      try {
        await api.post('/api/favorites', {
          rank: outfit.rank,
          item_ids: outfit.item_ids,
          items: outfit.items,
          compatibility_score: outfit.compatibility_score,
          explanation: outfit.explanation,
          occasion: state.stylist.occasion,
          temperature_c: state.stylist.temperature,
          rain: state.stylist.rain,
        });
        toast('Saved to Favorites', 'success');
      } catch (err) {
        toast(`Couldn't save favorite: ${err.message}`, 'error');
      }
    });
  
    const dateInline = resultsCol.querySelector('#dateInline');
    resultsCol.querySelector('#planDateToggle').addEventListener('click', () => {
      dateInline.classList.toggle('open');
    });
    resultsCol.querySelector('#confirmPlanBtn').addEventListener('click', async () => {
      const date = resultsCol.querySelector('#planDateInput').value;
      if (!date) return;
      try {
        const res = await api.post('/api/calendar', {
          date,
          item_ids: outfit.item_ids,
          items: outfit.items,
          occasion: state.stylist.occasion,
          compatibility_score: outfit.compatibility_score,
          reason: outfit.explanation || '',
          worn: false,
        });
        state.calendar[date] = (res && res.item) || {
          key: date,
          date,
          occasion: state.stylist.occasion,
          items: outfit.items,
          item_ids: outfit.item_ids,
          reason: outfit.explanation || '',
          worn: false,
        };
        toast(`Planned for ${date}`, 'success');
        dateInline.classList.remove('open');
      } catch (err) {
        toast(`Couldn't plan outfit: ${err.message}`, 'error');
      }
    });
  }
  
  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }
  
  /* ----------------------------------------------------------------
     CALENDAR
     ---------------------------------------------------------------- */
  
  document.getElementById('calPrev').addEventListener('click', () => { shiftMonth(-1); });
  document.getElementById('calNext').addEventListener('click', () => { shiftMonth(1); });
  document.getElementById('calToday').addEventListener('click', () => { state.calendarView = new Date(); renderCalendar(); });
  
  function shiftMonth(delta) {
    const d = state.calendarView;
    state.calendarView = new Date(d.getFullYear(), d.getMonth() + delta, 1);
    renderCalendar();
  }
  
  function getEntryItems(entry) {
    if (!entry) return [];
    const raw = (entry.items && entry.items.length ? entry.items : (entry.outfit && entry.outfit.items)) || [];
    if (raw.length) return raw;
    if (entry.item_ids && entry.item_ids.length && state.wardrobe.length) {
      return state.wardrobe.filter((w) => entry.item_ids.includes(w.id));
    }
    return [];
  }

  async function refreshCalendar() {
    try {
      const [entries] = await Promise.all([api.get('/api/calendar')]);
      state.calendar = entries.items || {};
    } catch (err) {
      state.calendar = {};
      toast(`Couldn't load calendar: ${err.message}`, 'error');
    }
    try {
      await loadWardrobe();
      if (!state.favorites.length) {
        const favData = await api.get('/api/favorites');
        state.favorites = favData.items || [];
      }
    } catch (_) { /* non-fatal */ }
    renderCalendar();
  }
  
  function dateKey(y, m, d) {
    return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  }
  
  function renderCalendar() {
    const view = state.calendarView;
    const year = view.getFullYear();
    const month = view.getMonth();
    document.getElementById('calMonthLabel').textContent = view.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  
    const firstDay = new Date(year, month, 1);
    const startOffset = firstDay.getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const todayKey = dateKey(new Date().getFullYear(), new Date().getMonth(), new Date().getDate());
  
    const grid = document.getElementById('calGrid');
    const dow = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    let html = dow.map((d) => `<div class="cal-dow tracked">${d}</div>`).join('');
  
    for (let i = 0; i < startOffset; i++) html += `<div class="cal-cell muted"></div>`;
  
    for (let day = 1; day <= daysInMonth; day++) {
      const key = dateKey(year, month, day);
      const entry = state.calendar[key];
      const plannedItems = getEntryItems(entry);
      const isToday = key === todayKey;
      html += `
        <div class="cal-cell ${isToday ? 'today' : ''} ${entry ? 'has-plan' : ''}" data-date="${key}">
          <div class="daynum">
            <span>${day}</span>
            ${entry ? (entry.worn ? '<span class="cal-worn-badge tracked">Worn</span>' : `<span style="font-size:9px;color:var(--scarlet);font-weight:600;" class="tracked">${escapeHtml(entry.occasion || 'Planned')}</span>`) : ''}
          </div>
          ${entry ? `
            <div class="cal-thumbs">
              ${plannedItems.slice(0, 3).map((it) => `<img src="${resolveUrl(it.url)}" alt="${escapeHtml(it.name || it.category || 'Saved dress')}" title="${escapeHtml(it.name || '')}" />`).join('')}
            </div>
            ${plannedItems[0] && plannedItems[0].name ? `<div class="cal-dress-label" title="${escapeHtml(plannedItems.map((i) => i.name).join(' + '))}">${escapeHtml(plannedItems[0].name)}</div>` : ''}
          ` : ''}
        </div>`;
    }
  
    grid.innerHTML = html;
    grid.querySelectorAll('.cal-cell[data-date]').forEach((cell) => {
      cell.addEventListener('click', () => openDayModal(cell.dataset.date));
    });
  }
  
  function openDayModal(key) {
    const entry = state.calendar[key];
    const title = document.getElementById('modalTitle');
    const sub = document.getElementById('modalSub');
    const body = document.getElementById('modalBody');
    const actions = document.getElementById('modalActions');
  
    const prettyDate = new Date(key + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
    title.textContent = prettyDate;
  
    if (entry) {
      const plannedItems = getEntryItems(entry);
      const reasonText = entry.reason || (entry.outfit && entry.outfit.reason) || '';
      sub.textContent = entry.occasion ? `Planned for ${entry.occasion}` : 'Planned outfit';
      body.innerHTML = `
        <div style="font-size:10.5px; text-transform:uppercase; letter-spacing:.08em; color:var(--charcoal-soft); margin-bottom:10px; font-weight:600;">
          Saved Dress / Outfit (${plannedItems.length} ${plannedItems.length === 1 ? 'piece' : 'pieces'})
        </div>
        <div class="featured-imgs">
          ${plannedItems.map((it) => `
            <div class="piece">
              <img src="${resolveUrl(it.url)}" alt="${escapeHtml(it.name || it.category || 'Saved dress')}" />
              <div class="piece-name">${escapeHtml(it.name || 'Saved Dress')}</div>
              <div class="piece-cat">${escapeHtml(it.category || it.group || '')}</div>
            </div>`).join('')}
        </div>
        ${reasonText ? `<div class="explanation" style="margin-bottom:16px;">"${escapeHtml(reasonText)}"</div>` : ''}
        <div class="worn-toggle-row">
          <span style="font-size:12px;">Mark as worn</span>
          <label class="switch"><input type="checkbox" id="wornCheckbox" ${entry.worn ? 'checked' : ''} /><span class="track"></span></label>
        </div>
      `;
      body.querySelector('#wornCheckbox').addEventListener('change', async (e) => {
        try {
          await api.patch(`/api/calendar/${key}`, { worn: e.target.checked });
          state.calendar[key].worn = e.target.checked;
          renderCalendar();
          toast(e.target.checked ? 'Marked as worn' : 'Marked as not worn', 'success');
        } catch (err) {
          toast(`Couldn't update: ${err.message}`, 'error');
          e.target.checked = !e.target.checked;
        }
      });
  
      actions.innerHTML = `
        <button class="text-btn danger" id="removePlanBtn">Remove</button>
        <button class="btn btn-ghost" id="changeOutfitBtn">Change outfit</button>
      `;
      actions.querySelector('#removePlanBtn').addEventListener('click', async () => {
        try {
          await api.del(`/api/calendar/${key}`);
          delete state.calendar[key];
          closeModal();
          renderCalendar();
          toast('Removed from calendar', 'success');
        } catch (err) {
          toast(`Couldn't remove: ${err.message}`, 'error');
        }
      });
      actions.querySelector('#changeOutfitBtn').addEventListener('click', () => openPickerModal(key));
    } else {
      sub.textContent = 'Nothing planned yet';
      body.innerHTML = `<div class="empty-state"><span class="serif">Free day</span>Plan an outfit for this date from your favorites or closet.</div>`;
      actions.innerHTML = `<button class="btn btn-primary" id="planNewBtn">Plan an outfit</button>`;
      actions.querySelector('#planNewBtn').addEventListener('click', () => openPickerModal(key));
    }
  
    openModal();
  }
  
  async function openPickerModal(key) {
    const title = document.getElementById('modalTitle');
    const sub = document.getElementById('modalSub');
    const body = document.getElementById('modalBody');
    const actions = document.getElementById('modalActions');
  
    title.textContent = 'Plan an outfit';
    sub.textContent = key;
  
    await loadWardrobe();
    try {
      const favData = await api.get('/api/favorites');
      state.favorites = favData.items || [];
    } catch (_) { /* keep cached */ }

    let mode = state.favorites.length ? 'favorites' : 'manual';
    let selectedFavorite = state.favorites.length ? state.favorites[0].id : null;
    const existingEntry = state.calendar[key];
    const existingIds = getEntryItems(existingEntry).map((i) => i.id).filter(Boolean);
    let selectedItems = new Set(existingIds);
  
    function render() {
      body.innerHTML = `
        <div class="tab-row">
          <button class="tab-btn ${mode === 'favorites' ? 'active' : ''}" data-mode="favorites">From Favorites</button>
          <button class="tab-btn ${mode === 'manual' ? 'active' : ''}" data-mode="manual">Pick from Closet</button>
        </div>
        <div id="pickerBody"></div>
      `;
      body.querySelectorAll('.tab-btn').forEach((b) => b.addEventListener('click', () => { mode = b.dataset.mode; render(); }));
  
      const pickerBody = body.querySelector('#pickerBody');
      if (mode === 'favorites') {
        if (!state.favorites.length) {
          pickerBody.innerHTML = `<div class="empty-state">No saved favorites yet — switch to "Pick from Closet", or save a look from the AI Stylist first.</div>`;
        } else {
          pickerBody.innerHTML = state.favorites.map((f) => `
            <div class="look-option ${selectedFavorite === f.id ? 'chosen' : ''}" data-id="${f.id}">
              <div class="mini-imgs">${(f.items || []).slice(0, 3).map((it) => `<img src="${resolveUrl(it.url)}" />`).join('')}</div>
              <div class="meta"><b>${escapeHtml(f.occasion || 'Outfit')}</b>${(f.items || []).map((it) => it.name).filter(Boolean).join(' + ')}</div>
            </div>`).join('');
          pickerBody.querySelectorAll('.look-option').forEach((el) => el.addEventListener('click', () => {
            selectedFavorite = el.dataset.id;
            render();
          }));
        }
      } else {
        pickerBody.innerHTML = `<div class="pick-item-grid">${state.wardrobe.map((it) => `
          <div class="pick-item ${selectedItems.has(it.id) ? 'selected' : ''}" data-id="${it.id}" title="${escapeHtml(it.name || '')}">
            <img src="${resolveUrl(it.url)}" alt="${escapeHtml(it.name || '')}" />
            <div class="pick-name">${escapeHtml(it.name || '')}</div>
          </div>`).join('')}</div>`;
        pickerBody.querySelectorAll('.pick-item').forEach((el) => el.addEventListener('click', () => {
          const id = el.dataset.id;
          if (selectedItems.has(id)) selectedItems.delete(id); else selectedItems.add(id);
          render();
        }));
      }
    }
    render();
  
    actions.innerHTML = `<button class="btn btn-primary" id="confirmPickBtn">Save to calendar</button>`;
    actions.querySelector('#confirmPickBtn').addEventListener('click', async () => {
      let payload;
      if (mode === 'favorites') {
        const fav = state.favorites.find((f) => f.id === selectedFavorite);
        if (!fav) { toast('Choose a favorite first', 'error'); return; }
        payload = { date: key, item_ids: fav.item_ids, items: fav.items, occasion: fav.occasion || 'casual', compatibility_score: fav.compatibility_score, reason: fav.explanation || '', worn: false };
      } else {
        if (!selectedItems.size) { toast('Select at least one item', 'error'); return; }
        const items = state.wardrobe.filter((w) => selectedItems.has(w.id));
        const inferredOcc = (items[0] && items[0].occasions && items[0].occasions[0]) || 'casual';
        payload = { date: key, item_ids: items.map((i) => i.id), items, occasion: inferredOcc, worn: false };
      }
      try {
        await api.post('/api/calendar', payload);
        const entries = await api.get('/api/calendar');
        state.calendar = entries.items || {};
        renderCalendar();
        openDayModal(key);
        toast('Outfit planned', 'success');
      } catch (err) {
        toast(`Couldn't plan outfit: ${err.message}`, 'error');
      }
    });
  
    openModal();
  }
  
  /* ----------------------------------------------------------------
     FAVORITES
     ---------------------------------------------------------------- */
  
  async function refreshFavorites() {
    const grid = document.getElementById('favGrid');
    const banner = document.getElementById('favoritesBanner');
    grid.innerHTML = Array.from({ length: 4 }).map(() => '<div class="fav-card skeleton" style="height:220px;"></div>').join('');
    try {
      const data = await api.get('/api/favorites');
      state.favorites = data.items || [];
      banner.innerHTML = '';
      renderFavorites();
    } catch (err) {
      banner.innerHTML = offlineBannerHtml();
      grid.innerHTML = '';
    }
  }
  
  function renderFavorites() {
    const grid = document.getElementById('favGrid');
    if (!state.favorites.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;">
        <span class="serif">No saved looks yet</span>
        Generate an outfit in the AI Stylist and save the ones you like.
        <div><button class="btn btn-primary" data-goto="stylist">Open AI Stylist</button></div>
      </div>`;
      grid.querySelector('[data-goto]').addEventListener('click', () => goto('stylist'));
      return;
    }
  
    grid.innerHTML = state.favorites.slice().reverse().map((f) => `
      <div class="fav-card" data-id="${f.id}">
        <div class="fav-imgs">${(f.items || []).map((it) => `<img src="${resolveUrl(it.url)}" />`).join('')}</div>
        <div class="fav-meta">
          <b>${escapeHtml(f.occasion || 'Outfit')}</b>
          ${f.compatibility_score ? Math.round(f.compatibility_score * 100) + '% match Â· ' : ''}saved ${f.saved_at ? new Date(f.saved_at).toLocaleDateString() : ''}
        </div>
        <div class="fav-actions">
          <button class="text-btn" data-action="plan">Plan a date</button>
          <button class="text-btn danger" data-action="remove">Remove</button>
        </div>
      </div>
    `).join('');
  
    grid.querySelectorAll('.fav-card').forEach((card) => {
      const id = card.dataset.id;
      const fav = state.favorites.find((f) => f.id === id);
      card.querySelector('[data-action="remove"]').addEventListener('click', async () => {
        try {
          await api.del(`/api/favorites/${id}`);
          state.favorites = state.favorites.filter((f) => f.id !== id);
          renderFavorites();
          toast('Removed from Favorites', 'success');
        } catch (err) {
          toast(`Couldn't remove: ${err.message}`, 'error');
        }
      });
      card.querySelector('[data-action="plan"]').addEventListener('click', () => {
        goto('calendar');
        const key = dateKey(new Date().getFullYear(), new Date().getMonth(), new Date().getDate());
        setTimeout(() => openPickerModalWithFavorite(key, fav), 150);
      });
    });
  }
  
  function openPickerModalWithFavorite(key, fav) {
    openPickerModal(key).then(() => {
      // Pre-select this favorite once the picker has rendered.
      setTimeout(() => {
        const el = document.querySelector(`.look-option[data-id="${fav.id}"]`);
        if (el) el.click();
      }, 60);
    });
  }
  
  /* ----------------------------------------------------------------
     HISTORY
     ---------------------------------------------------------------- */
  
  async function refreshHistory() {
    const list = document.getElementById('historyList');
    list.innerHTML = Array.from({ length: 3 }).map(() => '<div class="history-row"><div class="skeleton" style="height:42px;width:90px;"></div><div class="skeleton" style="height:14px;"></div></div>').join('');
    try {
      const data = await api.get('/api/history');
      state.history = data.items || [];
      renderHistory();
    } catch (err) {
      list.innerHTML = offlineBannerHtml();
    }
  }
  
  function renderHistory() {
    const list = document.getElementById('historyList');
    if (!state.history.length) {
      list.innerHTML = `<div class="empty-state">
        <span class="serif">No outfits marked as worn yet</span>
        Mark a planned outfit as "worn" on the Calendar to start building your history.
        <div><button class="btn btn-primary" data-goto="calendar">Open Calendar</button></div>
      </div>`;
      list.querySelector('[data-goto]').addEventListener('click', () => goto('calendar'));
      return;
    }
  
    list.innerHTML = state.history.map((h) => `
      <div class="history-row">
        <div class="hist-imgs">${(h.items || []).slice(0, 3).map((it) => `<img src="${resolveUrl(it.url)}" />`).join('')}</div>
        <div>
          <div class="hist-occasion">${escapeHtml(h.occasion || 'Outfit')}</div>
          ${h.compatibility_score ? `<div style="font-size:10.5px;color:var(--charcoal-soft);">${Math.round(h.compatibility_score * 100)}% match</div>` : ''}
        </div>
        <div class="hist-date">${new Date(h.date + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</div>
      </div>
    `).join('');
  }
  
  /* ----------------------------------------------------------------
     MULTI-USER & ACCOUNT MANAGEMENT
     ---------------------------------------------------------------- */

  function renderUserBar() {
    const user = state.currentUser;
    if (!user) return;

    const navAvatar = document.getElementById('navUserAvatar');
    const navName = document.getElementById('navUserName');
    const greeting = document.getElementById('dashboardGreeting');

    if (navAvatar) navAvatar.textContent = (user.name || user.username || 'U')[0].toUpperCase();
    if (navName) navName.textContent = user.name || user.username;

    if (greeting) {
      greeting.textContent = `Good to see you, ${user.name.split(' ')[0]}. Here is your wardrobe.`;
    }

    const personaBanner = document.getElementById('dashboardPersonaBanner');
    const userBio = document.getElementById('bannerUserBio');
    const userDetails = document.getElementById('bannerUserDetails');

    if (personaBanner) {
      personaBanner.style.display = 'flex';
      if (userBio) userBio.textContent = `“${user.bio || 'Curated wardrobe collection.'}”`;
      if (userDetails) {
        const colors = Array.isArray(user.preferred_colors) ? user.preferred_colors.join(', ') : (user.preferred_colors || '');
        userDetails.innerHTML = `
          <span><strong>Role:</strong> ${escapeHtml(user.role || 'Member')}</span>
          ${colors ? `<span><strong>Palette:</strong> ${escapeHtml(colors)}</span>` : ''}
          <span><strong>Temp Pref:</strong> ${escapeHtml(user.temp_pref || 'Balanced')}</span>
        `;
      }
    }
  }

  async function loadUsers() {
    try {
      const data = await api.get('/api/auth/users');
      state.usersList = data.users || [];
    } catch (err) {
      console.warn("Could not load users:", err);
    }
  }

  function clearUserSessionState() {
    state.wardrobe = [];
    state.stats = null;
    state.favorites = [];
    state.calendar = {};
    state.history = [];
    state.stylist.outfits = [];
    state.stylist.activeIndex = 0;
    state.pendingUpload = null;

    const rackGrid = document.getElementById('rackGrid');
    if (rackGrid) rackGrid.innerHTML = '';
    const recentGrid = document.getElementById('recentGrid');
    if (recentGrid) recentGrid.innerHTML = '';
    const resultsCol = document.getElementById('resultsCol');
    if (resultsCol) {
      resultsCol.innerHTML = `<div class="empty-state">
        <span class="serif">No looks yet</span>
        Set the occasion and temperature, then build.
      </div>`;
    }
  }

  function showWelcomeAuthMessage(message, type = 'error') {
    const box = document.getElementById('welcomeAuthMsg');
    if (!box) return;
    if (!message) {
      box.style.display = 'none';
      box.textContent = '';
      box.className = 'welcome-auth-msg';
      return;
    }
    box.textContent = message;
    box.className = `welcome-auth-msg ${type === 'success' ? 'success' : ''}`;
    box.style.display = 'block';
  }

  async function loginUserAccount(username, password) {
    try {
      showWelcomeAuthMessage('');
      const res = await api.post('/api/auth/login', { username, password });
      clearUserSessionState();
      state.currentUser = res.user;
      localStorage.setItem(TOKEN_KEY, String(res.user.id));
      localStorage.setItem(USER_KEY, JSON.stringify(res.user));
      toast(`Signed in as ${res.user.name}`, 'success');
      renderUserBar();
      await loadUsers();

      // Always land on Home when signing in
      goto('home');
      return res.user;
    } catch (err) {
      showWelcomeAuthMessage(`Sign in failed: ${err.message}`, 'error');
      toast(`Login failed: ${err.message}`, 'error');
      throw err;
    }
  }

  async function signupUserAccount(name, username, stylePersona, password) {
    try {
      showWelcomeAuthMessage('');
      const res = await api.post('/api/auth/signup', {
        name,
        username,
        password,
        style_persona: stylePersona || 'Personal & Chic'
      });
      clearUserSessionState();
      state.currentUser = res.user;
      localStorage.setItem(TOKEN_KEY, String(res.user.id));
      localStorage.setItem(USER_KEY, JSON.stringify(res.user));
      toast(`Account created! Welcome, ${res.user.name}`, 'success');
      renderUserBar();
      await loadUsers();

      goto('home');
      return res.user;
    } catch (err) {
      showWelcomeAuthMessage(`Sign up failed: ${err.message}`, 'error');
      toast(`Sign up failed: ${err.message}`, 'error');
      throw err;
    }
  }

  let welcomeTabController = null;

  function logout(initialTab = 'signin') {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    state.currentUser = null;
    clearUserSessionState();
    showWelcomeAuthMessage('');

    // Reset active room & nav tab to Home so next sign-in always starts on Home
    document.querySelectorAll('.room').forEach((r) => r.classList.remove('active'));
    document.querySelectorAll('.masthead-nav button').forEach((b) => b.classList.remove('active'));
    const homeRoom = document.getElementById('room-home');
    const homeNav = document.querySelector('.masthead-nav button[data-room="home"]');
    if (homeRoom) homeRoom.classList.add('active');
    if (homeNav) homeNav.classList.add('active');

    // Clear login inputs
    const loginUser = document.getElementById('loginUsernameInput');
    const loginPass = document.getElementById('loginPasswordInput');
    if (loginUser) loginUser.value = '';
    if (loginPass) loginPass.value = '';

    // Show sign-in / sign-up screen
    const screen = document.getElementById('welcomeScreen');
    if (screen) {
      screen.classList.remove('leaving');
      screen.classList.remove('hidden');
    }
    document.body.classList.add('pre-entry');

    if (welcomeTabController) {
      if (initialTab === 'signup') {
        welcomeTabController.showSignUp(true);
      } else {
        welcomeTabController.showSignIn();
      }
    }

    // Reset avatar and user display in nav
    const avatar = document.getElementById('navUserAvatar');
    const nameEl = document.getElementById('navUserName');
    if (avatar) avatar.textContent = '—';
    if (nameEl) nameEl.textContent = 'Account Sign In';

    // Clear views
    const rackGrid = document.getElementById('rackGrid');
    if (rackGrid) rackGrid.innerHTML = '';
    const recentGrid = document.getElementById('recentGrid');
    if (recentGrid) recentGrid.innerHTML = '';
    const resultsCol = document.getElementById('resultsCol');
    if (resultsCol) resultsCol.innerHTML = '';
  }

  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      logout('signin');
      toast('Logged out successfully', 'info');
    });
  }

  const navSignUpBtn = document.getElementById('navSignUpBtn');
  if (navSignUpBtn) {
    navSignUpBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      logout('signup');
    });
  }

  const bannerLogoutBtn = document.getElementById('bannerLogoutBtn');
  if (bannerLogoutBtn) {
    bannerLogoutBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      logout('signin');
      toast('Logged out successfully', 'info');
    });
  }

  /* ----------------------------------------------------------------
     ACCOUNT SIGN IN & SIGN UP SCREEN
     ---------------------------------------------------------------- */

  function initWelcomeScreen() {
    const screen = document.getElementById('welcomeScreen');
    const tabSignIn = document.getElementById('tabSignIn');
    const tabSignUp = document.getElementById('tabSignUp');
    const signInForm = document.getElementById('signInForm');
    const signUpForm = document.getElementById('signUpForm');

    const loginUser = document.getElementById('loginUsernameInput');
    const loginPass = document.getElementById('loginPasswordInput');
    const loginBtn = document.getElementById('welcomeLoginBtn');

    const signupName = document.getElementById('signupNameInput');
    const signupUser = document.getElementById('signupUsernameInput');
    const signupPass = document.getElementById('signupPasswordInput');
    const signupBtn = document.getElementById('welcomeSignupBtn');

    const linkToSignUp = document.getElementById('linkToSignUp');
    const linkToSignIn = document.getElementById('linkToSignIn');

    const eyebrow = document.getElementById('welcomeEyebrow');
    const tagline = document.getElementById('welcomeTagline');

    function showSignIn() {
      showWelcomeAuthMessage('');
      if (tabSignIn) tabSignIn.classList.add('active');
      if (tabSignUp) tabSignUp.classList.remove('active');
      if (signInForm) signInForm.style.display = 'flex';
      if (signUpForm) signUpForm.style.display = 'none';
      if (eyebrow) eyebrow.textContent = 'Account Sign In';
      if (tagline) tagline.textContent = 'Sign in to your personal wardrobe account.';
      if (loginUser) loginUser.focus();
    }

    function showSignUp(clearFields = false) {
      showWelcomeAuthMessage('');
      if (tabSignUp) tabSignUp.classList.add('active');
      if (tabSignIn) tabSignIn.classList.remove('active');
      if (signUpForm) signUpForm.style.display = 'flex';
      if (signInForm) signInForm.style.display = 'none';
      if (eyebrow) eyebrow.textContent = 'Create Account';
      if (tagline) tagline.textContent = 'Create your personal wardrobe account.';

      if (clearFields) {
        if (signupName) signupName.value = '';
        if (signupUser) signupUser.value = '';
        if (signupPass) signupPass.value = '';
      } else {
        // Carry over any typed username/password from Sign In if Sign Up fields are empty
        if (loginUser && loginUser.value.trim() && signupUser && !signupUser.value.trim()) {
          signupUser.value = loginUser.value.trim();
        }
        if (loginPass && loginPass.value && signupPass && !signupPass.value) {
          signupPass.value = loginPass.value;
        }
      }
      if (signupName) signupName.focus();
    }

    welcomeTabController = { showSignIn, showSignUp };

    if (tabSignIn) tabSignIn.addEventListener('click', () => showSignIn());
    if (tabSignUp) tabSignUp.addEventListener('click', () => showSignUp(false));
    if (linkToSignUp) linkToSignUp.addEventListener('click', () => showSignUp(false));
    if (linkToSignIn) linkToSignIn.addEventListener('click', () => showSignIn());

    if (state.currentUser) {
      if (screen) screen.classList.add('hidden');
      document.body.classList.remove('pre-entry');
    } else {
      document.body.classList.add('pre-entry');
      if (screen) {
        screen.classList.remove('hidden');
        screen.classList.remove('leaving');
      }
    }

    async function handleLogin() {
      const username = loginUser ? loginUser.value.trim() : '';
      const password = loginPass ? loginPass.value : '';

      if (!username || !password) {
        showWelcomeAuthMessage("Please enter both username and password.", "error");
        toast("Please enter both username and password", "error");
        return;
      }

      if (loginBtn) loginBtn.disabled = true;
      try {
        await loginUserAccount(username, password);
        if (screen) screen.classList.add('leaving');
        document.body.classList.remove('pre-entry');
        setTimeout(() => {
          if (screen) screen.classList.add('hidden');
        }, 600);
      } catch (err) {
        // notification already fired in loginUserAccount
      } finally {
        if (loginBtn) loginBtn.disabled = false;
      }
    }

    async function handleSignup() {
      let name = signupName ? signupName.value.trim() : '';
      let username = signupUser ? signupUser.value.trim() : '';
      const password = signupPass ? signupPass.value : '';

      // Auto-derive name from username or username from name if one was left blank
      if (!name && username) {
        name = username.replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      }
      if (!username && name) {
        username = name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
      }

      if (!username || !password) {
        showWelcomeAuthMessage("Please enter a username (or full name) and a password.", "error");
        toast("Please enter a username and password", "error");
        return;
      }

      const btnSpan = signupBtn ? signupBtn.querySelector('span') : null;
      const origText = btnSpan ? btnSpan.textContent : 'Create Account';
      if (signupBtn) signupBtn.disabled = true;
      if (btnSpan) btnSpan.textContent = 'Creating Account…';

      try {
        await signupUserAccount(name, username, 'Personal & Chic', password);
        if (signupName) signupName.value = '';
        if (signupUser) signupUser.value = '';
        if (signupPass) signupPass.value = '';
        if (screen) screen.classList.add('leaving');
        document.body.classList.remove('pre-entry');
        setTimeout(() => {
          if (screen) screen.classList.add('hidden');
        }, 600);
      } catch (err) {
        // notification already fired in signupUserAccount
      } finally {
        if (signupBtn) signupBtn.disabled = false;
        if (btnSpan) btnSpan.textContent = origText;
      }
    }

    if (loginBtn) loginBtn.addEventListener('click', handleLogin);
    if (loginPass) loginPass.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleLogin(); });
    if (loginUser) loginUser.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleLogin(); });

    if (signupBtn) signupBtn.addEventListener('click', handleSignup);
    if (signupName) signupName.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSignup(); });
    if (signupUser) signupUser.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSignup(); });
    if (signupPass) signupPass.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSignup(); });
  }

  /* ----------------------------------------------------------------
     INIT
     ---------------------------------------------------------------- */

  (async function init() {
    await checkHealth();
    await loadUsers();

    // Check if previously logged in with valid token
    const cached = localStorage.getItem(USER_KEY);
    const token = localStorage.getItem(TOKEN_KEY);
    if (cached && token) {
      try {
        state.currentUser = JSON.parse(cached);
      } catch (_) {
        state.currentUser = null;
      }
    } else {
      state.currentUser = null;
    }

    initWelcomeScreen();
    if (state.currentUser) {
      renderUserBar();
      refreshDashboard();
    }
  })();
