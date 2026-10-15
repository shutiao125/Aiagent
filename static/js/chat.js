/**
 * iframe 答疑窗口：历史回溯、SSE 流式打字机、停止生成、Markdown 渲染。
 */
(function () {
  marked.setOptions({ breaks: true, gfm: true });

  const streamEl = document.getElementById('message-stream');
  const titleEl = document.getElementById('chat-title');
  const modeTag = document.getElementById('mode-tag');
  const inputEl = document.getElementById('chat-input');
  const sendBtn = document.getElementById('btn-send');
  const stopBtn = document.getElementById('btn-stop');
  const thinkBtn = document.getElementById('btn-deep-thinking');
  const composer = document.getElementById('composer');

  const conversationId = Number(new URLSearchParams(location.search).get('id'));
  // deepThinking：深度思考开关，选择记忆在 localStorage，默认关闭（普通直答）
  const state = {
    streaming: false,
    abortController: null,
    deepThinking: localStorage.getItem('ai_deep_thinking') === '1',
  };
  // null=健康检查未返回（先按真实模型处理），true=MOCK，false=真实 Doubao
  let isMockMode = null;

  /* ---------------- 渲染 ---------------- */
  function renderMarkdown(text) {
    const rawHtml = marked.parse(text || '');
    return DOMPurify.sanitize(rawHtml);
  }

  function scrollToBottom() {
    streamEl.scrollTop = streamEl.scrollHeight;
  }

  function createMessageRow(role) {
    const row = document.createElement('div');
    row.className = `message-row ${role} message-inner`;
    const body = document.createElement('div');
    body.className = 'msg-body';
    const roleName = document.createElement('div');
    roleName.className = 'msg-role';
    roleName.textContent = role === 'user' ? '我' : 'AI 助手';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    body.appendChild(roleName);
    body.appendChild(bubble);
    // 用户消息不显示头像（气泡右对齐），仅 AI 侧保留头像
    if (role === 'assistant') {
      const avatar = document.createElement('div');
      avatar.className = `avatar ${role}`;
      avatar.textContent = 'AI';
      row.appendChild(avatar);
    }
    row.appendChild(body);
    return { row, bubble };
  }

  function appendUserMessage(text) {
    const { row, bubble } = createMessageRow('user');
    bubble.style.whiteSpace = 'pre-wrap';
    bubble.textContent = text;
    streamEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  function appendAssistantMessage() {
    const { row, bubble } = createMessageRow('assistant');
    streamEl.appendChild(row);
    return bubble;
  }

  /* 流式发送后立即占位：开启深度思考且为真实模型时显示「深度思考中」，
     否则（普通模式/MOCK）显示输入圆点；返回 bubble 内各区域的句柄。 */
  function createPendingAssistant() {
    const { row, bubble } = createMessageRow('assistant');
    let thinkingBox = null;
    let thinkingText = null;
    if (state.deepThinking && !isMockMode) {
      thinkingBox = document.createElement('div');
      thinkingBox.className = 'thinking-live';
      thinkingBox.innerHTML =
        '<div class="thinking-header"><span class="thinking-spinner"></span>正在深度思考…</div>' +
        '<div class="thinking-text"></div>';
      thinkingText = thinkingBox.querySelector('.thinking-text');
      bubble.appendChild(thinkingBox);
    } else {
      const dots = document.createElement('div');
      dots.className = 'typing-dots';
      dots.innerHTML = '<i></i><i></i><i></i>';
      bubble.appendChild(dots);
      bubble._typingDots = dots;
    }
    const answerEl = document.createElement('div');
    answerEl.className = 'answer-content';
    bubble.appendChild(answerEl);
    streamEl.appendChild(row);
    scrollToBottom();
    return { row, bubble, answerEl, thinkingBox, thinkingText };
  }

  /* 思考结束（首个正式字块 / 结束收尾）：实时思考块 → 可折叠记录 */
  function collapseThinking(pending) {
    if (!pending.thinkingBox) return;
    const raw = pending.thinkingText.textContent || '';
    const fold = document.createElement('details');
    fold.className = 'reasoning-fold';
    const summary = document.createElement('summary');
    summary.textContent = '已深度思考' + (raw ? `（${raw.length} 字）` : '') + '，点击展开';
    const pre = document.createElement('div');
    pre.className = 'reasoning-text';
    pre.textContent = raw;
    fold.appendChild(summary);
    fold.appendChild(pre);
    pending.thinkingBox.replaceWith(fold);
    pending.thinkingBox = null;
    pending.thinkingText = null;
  }

  function removeTypingDots(pending) {
    if (pending.bubble._typingDots) {
      pending.bubble._typingDots.remove();
      pending.bubble._typingDots = null;
    }
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function showWelcome() {
    streamEl.innerHTML = `
      <div class="chat-welcome">
        <div>
          <div class="icon">✦</div>
          <h2>有什么可以帮你？</h2>
          <div>输入问题开始与 AI 助手对话，支持多轮上下文</div>
          <div class="tips">
            <span class="tip">Enter 发送</span>
            <span class="tip">Shift+Enter 换行</span>
            <span class="tip">深度思考可开关</span>
            <span class="tip">历史自动保存</span>
          </div>
        </div>
      </div>`;
  }

  function renderHistory(messages) {
    if (!messages.length) { showWelcome(); return; }
    streamEl.innerHTML = '';
    for (const m of messages) {
      if (m.role === 'user') {
        appendUserMessage(m.content);
      } else if (m.role === 'assistant') {
        const bubble = appendAssistantMessage();
        bubble.innerHTML = renderMarkdown(m.content);
      }
    }
    streamEl.scrollTop = streamEl.scrollHeight;
  }

  /* ---------------- 发送 ---------------- */
  function setSending(sending) {
    state.streaming = sending;
    composer.classList.toggle('sending', sending);
    sendBtn.disabled = sending || !inputEl.value.trim();
    thinkBtn.disabled = sending || isMockMode === true;
    inputEl.disabled = false;
  }

  /* 深度思考开关：UI 态 + localStorage 持久化 */
  function updateThinkToggle() {
    thinkBtn.classList.toggle('active', state.deepThinking);
    thinkBtn.setAttribute('aria-pressed', state.deepThinking ? 'true' : 'false');
  }
  thinkBtn.addEventListener('click', () => {
    if (state.streaming) return;
    state.deepThinking = !state.deepThinking;
    localStorage.setItem('ai_deep_thinking', state.deepThinking ? '1' : '0');
    updateThinkToggle();
  });

  async function send() {
    const text = inputEl.value.trim();
    if (!text || state.streaming) return;

    inputEl.value = '';
    autoResize();
    setSending(true);

    // 乐观渲染用户消息
    let userRow = null;
    {
      const welcome = streamEl.querySelector('.chat-welcome');
      if (welcome) streamEl.innerHTML = '';
      const built = createMessageRow('user');
      userRow = built.row;
      built.bubble.style.whiteSpace = 'pre-wrap';
      built.bubble.textContent = text;
      streamEl.appendChild(userRow);
      scrollToBottom();
    }

    // 立即创建 AI 占位气泡（思考态/输入指示），避免请求期间界面无反馈
    const pending = createPendingAssistant();
    let collected = '';
    let interrupted = false;

    const stopNoteHtml = '<div class="stopped-note">— 已停止生成</div>';

    state.abortController = window.sendMessageStream(conversationId, text, {
      meta() {},
      thinking(data) {
        // 深度思考阶段：实时展示思考文本，不渲染 Markdown
        if (pending.thinkingText) {
          pending.thinkingText.textContent += data.content || '';
          scrollToBottom();
        }
      },
      delta(data) {
        if (!collected) {
          // 首个正式字块：收起思考态/移除输入指示
          collapseThinking(pending);
          removeTypingDots(pending);
        }
        collected += data.content || '';
        pending.answerEl.innerHTML =
          renderMarkdown(collected) + '<span class="typing-cursor"></span>';
        scrollToBottom();
      },
      error(data) {
        interrupted = true;
        removeTypingDots(pending);
        if (collected) {
          collapseThinking(pending);
          pending.answerEl.innerHTML =
            renderMarkdown(collected) +
            `<div class="error-note">⚠️ ${escapeHtml(data.message)}</div>`;
        } else if (pending.thinkingText && pending.thinkingText.textContent) {
          // 思考完成后/过程中出错：保留思考记录，错误以 toast 提示
          collapseThinking(pending);
          toast(data.message, 'error');
        } else {
          pending.row.remove();
          toast(data.message, 'error');
        }
      },
      done() {
        finish();
      },
    }, state.deepThinking);

    stopBtn.onclick = () => {
      if (state.abortController) state.abortController.abort();
      interrupted = true;
      finish(true);
    };

    function finish(stoppedByUser) {
      if (finish._called) return;
      finish._called = true;
      clearTimeout(fallbackTimer);
      removeTypingDots(pending);
      if (collected) {
        collapseThinking(pending);
        pending.answerEl.innerHTML =
          renderMarkdown(collected) + (stoppedByUser ? stopNoteHtml : '');
      } else if (stoppedByUser) {
        // 思考阶段被用户停止：折叠保留思考过程
        collapseThinking(pending);
        if (!pending.bubble.querySelector('.reasoning-fold')) pending.row.remove();
        else pending.answerEl.innerHTML = stopNoteHtml;
      } else {
        // 服务端正常结束但无任何正文（极端情况）：有思考则折叠保留，否则移除空气泡
        collapseThinking(pending);
        if (!pending.bubble.querySelector('.reasoning-fold')) pending.row.remove();
      }
      setSending(false);
      inputEl.focus();
      refreshTitleAndNotify();
    }

    // 兜底收尾（服务端正常 done 与本地 stop 都会提前 clearTimeout）
    const fallbackTimer = setTimeout(() => { if (state.streaming) finish(); }, 5 * 60 * 1000);
  }

  async function refreshTitleAndNotify() {
    try {
      const conv = await API.getConversation(conversationId);
      titleEl.textContent = conv.title || 'AI 对话';
    } catch (_e) { /* ignore */ }
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type: 'conversation-updated', conversationId }, '*');
    }
  }

  /* ---------------- 输入交互 ---------------- */
  function autoResize() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
  }

  inputEl.addEventListener('input', () => {
    autoResize();
    sendBtn.disabled = state.streaming || !inputEl.value.trim();
  });
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send();
    }
  });
  sendBtn.addEventListener('click', send);

  /* ---------------- 初始化 ---------------- */
  function showMissingConversation() {
    titleEl.textContent = '会话不可用';
    streamEl.innerHTML = `
      <div class="chat-welcome">
        <div>
          <div class="icon">🗂️</div>
          <h2>该会话不存在或已被删除</h2>
          <div>请从左侧会话列表重新选择，或新建一个对话</div>
          <div class="tips"><a class="back-link" href="/">← 返回会话列表</a></div>
        </div>
      </div>`;
    inputEl.disabled = true;
    sendBtn.disabled = true;
    thinkBtn.disabled = true;
    // 通知父页面：iframe 内的会话已失效，清空选中态与遮罩
    if (window.parent && window.parent !== window) {
      window.parent.postMessage(
        { type: 'conversation-missing', conversationId }, '*');
    }
  }

  async function init() {
    if (!conversationId) {
      streamEl.innerHTML = '<div class="chat-welcome"><div><div class="icon">💬</div><h2>尚未选择会话</h2><div>请点击左侧「新建会话」开始对话</div></div></div>';
      inputEl.disabled = true;
      sendBtn.disabled = true;
      thinkBtn.disabled = true;
      return;
    }
    try {
      // 先确认会话存在，再拉历史：避免会话失效时并发产生多个 404
      const conv = await API.getConversation(conversationId);
      const messages = await API.getMessages(conversationId);
      titleEl.textContent = conv.title || 'AI 对话';
      renderHistory(messages);
    } catch (e) {
      if (e && e.code === 4004) {
        showMissingConversation();
        return;
      }
      streamEl.innerHTML =
        `<div class="chat-welcome"><div><h2>加载失败</h2><div>${escapeHtml(e.message)}</div></div></div>`;
    }
    inputEl.focus();
  }

  // 模式标签由健康接口给出
  fetch('/api/health').then((r) => r.json()).then((b) => {
    if (b && b.data) {
      isMockMode = b.data.llm_mode === 'mock';
      modeTag.textContent = isMockMode ? 'MOCK 模式' : 'Doubao';
      if (isMockMode) {
        // MOCK 模式没有真正的思考能力，禁用开关并提示
        thinkBtn.disabled = true;
        thinkBtn.title = 'MOCK 模拟模式下不支持深度思考，配置真实模型后可用';
      }
      updateThinkToggle();
    }
  }).catch(() => {});

  updateThinkToggle();
  init();
})();
