/**
 * 主控台：左侧全局导航 + 答疑视图会话管理 + 通用弹窗/工具。
 * 其余业务模块（basic / assignments / generate）通过 window.AppUI 与 AppNav 协作。
 */
(function () {
  const listEl = document.getElementById('conv-list');
  const frame = document.getElementById('chat-frame');
  const emptyMask = document.getElementById('chat-empty-mask');

  const state = { conversations: [], currentId: null };

  /* ---------- 公共工具 ---------- */
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function fmtTime(t) {
    if (!t) return '';
    const d = new Date(String(t).replace(/-/g, '/'));
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    if (d.toDateString() === now.toDateString()) {
      return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
    return `${d.getMonth() + 1}/${d.getDate()}`;
  }

  function fmtFull(t) {
    if (!t) return '';
    const d = new Date(String(t).replace(/-/g, '/'));
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function openModal(id) { document.getElementById(id).classList.add('show'); }
  function closeModal(id) { document.getElementById(id).classList.remove('show'); }

  function openConfirm(title, message) {
    return new Promise((resolve) => {
      document.getElementById('confirm-title').textContent = title;
      document.getElementById('confirm-message').textContent = message;
      const mask = document.getElementById('confirm-modal');
      mask.classList.add('show');
      const done = (ok) => {
        mask.classList.remove('show');
        okBtn.onclick = null; cancelBtn.onclick = null;
        resolve(ok);
      };
      const okBtn = document.getElementById('confirm-ok');
      const cancelBtn = document.getElementById('confirm-cancel');
      okBtn.onclick = () => done(true);
      cancelBtn.onclick = () => done(false);
    });
  }

  function openRename(currentTitle) {
    return new Promise((resolve) => {
      const input = document.getElementById('rename-input');
      const mask = document.getElementById('rename-modal');
      input.value = currentTitle || '';
      mask.classList.add('show');
      setTimeout(() => { input.focus(); input.select(); }, 30);
      const done = (val) => { mask.classList.remove('show'); resolve(val); };
      document.getElementById('rename-ok').onclick = () => done(input.value.trim());
      document.getElementById('rename-cancel').onclick = () => done(null);
      input.onkeydown = (e) => { if (e.key === 'Enter') done(input.value.trim()); };
    });
  }

  /* ---------- 全局导航 ---------- */
  const viewHooks = {};
  function onViewShow(view, fn) { viewHooks[view] = fn; }

  function switchView(view) {
    document.querySelectorAll('.nav-item').forEach((t) => {
      t.classList.toggle('active', t.dataset.view === view);
    });
    document.querySelectorAll('#main > .view').forEach((sec) => {
      sec.classList.toggle('active', sec.id === `view-${view}`);
    });
    if (viewHooks[view]) viewHooks[view]();
  }

  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', () => switchView(item.dataset.view));
  });

  /* ---------- 答疑：会话列表 ---------- */
  async function loadConversations(keepSelect) {
    try {
      state.conversations = await API.listConversations();
    } catch (e) {
      toast(e.message, 'error');
      state.conversations = [];
    }
    renderList();
    if (keepSelect && state.currentId
        && !state.conversations.some((c) => c.id === state.currentId)) {
      state.currentId = null;
      frame.src = 'about:blank';
    }
    syncEmpty();
  }

  function renderList() {
    if (!state.conversations.length) {
      listEl.innerHTML = '<div class="conv-empty">暂无会话，点击上方按钮新建</div>';
      return;
    }
    listEl.innerHTML = state.conversations.map((c) => `
      <div class="conv-item ${c.id === state.currentId ? 'active' : ''}" data-id="${c.id}">
        <div class="conv-title">
          ${c.pinned ? '<span class="pin-flag">📌</span>' : ''}${escapeHtml(c.title || '新会话')}
        </div>
        <div class="conv-meta">${fmtTime(c.updated_at)} · ${escapeHtml(c.last_preview || '开始新对话')}</div>
        <div class="conv-actions">
          <button class="conv-icon-btn" data-act="pin" title="${c.pinned ? '取消置顶' : '置顶'}">${c.pinned ? '📍' : '📌'}</button>
          <button class="conv-icon-btn" data-act="rename" title="重命名">✏️</button>
          <button class="conv-icon-btn danger" data-act="delete" title="删除">🗑️</button>
        </div>
      </div>
    `).join('');
  }

  function syncEmpty() {
    emptyMask.style.display = state.currentId ? 'none' : 'grid';
  }

  function selectConversation(id) {
    state.currentId = id;
    frame.src = `/chat.html?id=${id}`;
    renderList();
    syncEmpty();
  }

  async function createConversation() {
    try {
      const conv = await API.createConversation(null);
      await loadConversations();
      selectConversation(conv.id);
    } catch (e) {
      toast(e.message, 'error');
    }
  }

  document.getElementById('btn-new-chat').addEventListener('click', createConversation);

  listEl.addEventListener('click', async (e) => {
    const item = e.target.closest('.conv-item');
    if (!item) return;
    const id = Number(item.dataset.id);
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (!act) { selectConversation(id); return; }
    e.stopPropagation();
    const conv = state.conversations.find((c) => c.id === id);
    try {
      if (act === 'pin') {
        await API.pinConversation(id, !conv.pinned);
        await loadConversations(true);
      } else if (act === 'rename') {
        const title = await openRename(conv.title);
        if (title) {
          await API.renameConversation(id, title);
          await loadConversations(true);
          toast('已重命名', 'success');
        }
      } else if (act === 'delete') {
        const ok = await openConfirm(
          '删除会话',
          `确定删除会话「${conv.title}」吗？该会话的全部聊天记录将一并删除，且不可恢复。`
        );
        if (ok) {
          await API.deleteConversation(id);
          if (state.currentId === id) {
            state.currentId = null;
            frame.src = 'about:blank';
          }
          await loadConversations();
          syncEmpty();
          toast('会话已删除', 'success');
        }
      }
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  /* iframe 内对话变化通知 → 刷新列表；会话失效 → 清空选中态 */
  window.addEventListener('message', (e) => {
    if (!e.data) return;
    if (e.data.type === 'conversation-updated') {
      loadConversations(true);
    } else if (e.data.type === 'conversation-missing') {
      if (state.currentId && state.currentId === e.data.conversationId) {
        state.currentId = null;
        frame.src = 'about:blank';
      }
      loadConversations(true);
    }
  });

  /* ---------- 侧栏模型状态 ---------- */
  fetch('/api/health').then((r) => r.json()).then((b) => {
    const el = document.getElementById('sidebar-mode');
    if (!b || !b.data) return;
    if (b.data.llm_mode === 'mock') {
      el.textContent = 'MOCK 模拟模式';
      el.parentElement.classList.add('mode-mock');
    } else {
      el.textContent = `Doubao · ${b.data.model || ''}`;
    }
    el.parentElement.classList.add('mode-ok');
  }).catch(() => {
    const el = document.getElementById('sidebar-mode');
    el.textContent = '服务未连接';
    el.parentElement.classList.add('mode-err');
  });

  /* 对外共享 */
  window.AppUI = {
    escapeHtml, fmtTime, fmtFull,
    openModal, closeModal, openConfirm,
    onViewShow,
  };
  window.AppNav = { switch: switchView };

  /* 初始化 */
  loadConversations();

  /* 首次加载补触发初始视图钩子：
     首页等模块的数据加载都通过 onViewShow 注册，
     仅在 switchView 时执行；页面初次进入时默认视图是 CSS 直接显示的，
     若不补触发，必须手动切走再切回才会加载数据。
     放到 DOMContentLoaded：此时 app/basic/assignments 等脚本均已完成钩子注册。 */
  window.addEventListener('DOMContentLoaded', () => {
    const initial = document.querySelector('.nav-item.active')?.dataset.view || 'home';
    switchView(initial);
  });
})();
