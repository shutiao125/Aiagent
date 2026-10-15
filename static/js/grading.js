/**
 * 教师批改：待批/已批两个子页签 + 逐题批改工作台。
 * 客观题（选择/判断/填空）由 AI 预批，老师可改判改分；主观题（简答）老师打分。
 */
(function () {
  const { escapeHtml, fmtTime, fmtFull, onViewShow } = window.AppUI;

  const TYPE_LABELS = {
    single: '单选题', multiple: '多选题', judge: '判断题',
    fill: '填空题', short: '简答题',
  };
  const CHOICE = { single: true, multiple: true, judge: true };

  const listPane = document.getElementById('assignment-list-pane');
  const detailPane = document.getElementById('assignment-detail-pane');
  const gradingPane = document.getElementById('grading-pane');
  const tabsEl = document.getElementById('assign-sub-tabs');
  const tabPanes = {
    list: document.getElementById('pane-tab-list'),
    pending: document.getElementById('pane-tab-pending'),
    graded: document.getElementById('pane-tab-graded'),
  };
  const pendingTbody = document.getElementById('pending-tbody');
  const gradedTbody = document.getElementById('graded-tbody');
  const badgeEl = document.getElementById('tab-pending-count');

  let activeTab = 'list';
  let returnTab = 'pending';
  let currentDetail = null;

  /* ================= 子页签 ================= */
  function switchTab(name) {
    activeTab = name;
    tabsEl.querySelectorAll('.sub-tab').forEach((b) => {
      b.classList.toggle('active', b.dataset.pane === name);
    });
    Object.entries(tabPanes).forEach(([k, el]) => {
      el.style.display = k === name ? '' : 'none';
    });
    if (name === 'pending') loadPending();
    if (name === 'graded') loadGraded();
    refreshBadge();
  }

  async function refreshBadge() {
    try {
      const res = await API.gradingPendingCount();
      const n = res.count || 0;
      badgeEl.textContent = n;
      badgeEl.style.display = n ? '' : 'none';
    } catch (_e) { /* 忽略角标失败 */ }
  }

  function openTab(name, opts) {
    opts = opts || {};
    if (opts.keyword !== undefined) {
      document.getElementById(name === 'graded' ? 'graded-keyword' : 'pending-keyword').value = opts.keyword;
    }
    gradingPane.style.display = 'none';
    detailPane.style.display = 'none';
    listPane.style.display = '';
    switchTab(name);
  }

  tabsEl.addEventListener('click', (e) => {
    const btn = e.target.closest('.sub-tab');
    if (btn) switchTab(btn.dataset.pane);
  });

  /* ================= 列表 ================= */
  function listParams(prefix) {
    const params = {};
    const classId = document.getElementById(`${prefix}-filter-class`).value;
    const keyword = document.getElementById(`${prefix}-keyword`).value.trim();
    if (classId) params.class_id = classId;
    if (keyword) params.keyword = keyword;
    return params;
  }

  async function loadPending() {
    window.BasicData.fillSelect(document.getElementById('pending-filter-class'), 'class', '全部班级');
    pendingTbody.innerHTML = '<tr><td colspan="8" class="empty-cell">加载中…</td></tr>';
    try {
      const rows = await API.gradingList({ status: 'pending', ...listParams('pending') });
      if (!rows.length) {
        pendingTbody.innerHTML = '<tr><td colspan="8" class="empty-cell">暂无待批作业 🎉</td></tr>';
        return;
      }
      pendingTbody.innerHTML = rows.map((s) => `
        <tr>
          <td><span class="cell-title">${escapeHtml(s.student_name)}</span></td>
          <td>${escapeHtml(s.student_no || '-')}</td>
          <td>${escapeHtml(s.assignment_title)}</td>
          <td>${escapeHtml(s.class_name || '-')}</td>
          <td>${fmtTime(s.submitted_at)}</td>
          <td>${s.answer_count - s.pending_count}/${s.answer_count} 题已批</td>
          <td>${s.total_score} / ${s.max_score}</td>
          <td><button class="link-btn" data-gact="open" data-id="${s.id}">批改</button></td>
        </tr>`).join('');
    } catch (e) {
      pendingTbody.innerHTML = `<tr><td colspan="8" class="empty-cell">加载失败：${escapeHtml(e.message)}</td></tr>`;
    }
  }

  async function loadGraded() {
    window.BasicData.fillSelect(document.getElementById('graded-filter-class'), 'class', '全部班级');
    gradedTbody.innerHTML = '<tr><td colspan="7" class="empty-cell">加载中…</td></tr>';
    try {
      const rows = await API.gradingList({ status: 'graded', ...listParams('graded') });
      if (!rows.length) {
        gradedTbody.innerHTML = '<tr><td colspan="7" class="empty-cell">暂无已批作业</td></tr>';
        return;
      }
      gradedTbody.innerHTML = rows.map((s) => `
        <tr>
          <td><span class="cell-title">${escapeHtml(s.student_name)}</span></td>
          <td>${escapeHtml(s.student_no || '-')}</td>
          <td>${escapeHtml(s.assignment_title)}</td>
          <td>${escapeHtml(s.class_name || '-')}</td>
          <td>${fmtTime(s.graded_at || s.submitted_at)}</td>
          <td><b>${s.total_score}</b> / ${s.max_score}</td>
          <td><button class="link-btn" data-gact="open" data-id="${s.id}">查看 / 复批</button></td>
        </tr>`).join('');
    } catch (e) {
      gradedTbody.innerHTML = `<tr><td colspan="7" class="empty-cell">加载失败：${escapeHtml(e.message)}</td></tr>`;
    }
  }

  ['pending', 'graded'].forEach((name) => {
    document.getElementById(`btn-${name}-search`).addEventListener('click',
      name === 'pending' ? loadPending : loadGraded);
    document.getElementById(`${name}-keyword`).addEventListener('keydown', (e) => {
      if (e.key === 'Enter') (name === 'pending' ? loadPending : loadGraded)();
    });
    document.getElementById(`${name}-filter-class`).addEventListener('change',
      name === 'pending' ? loadPending : loadGraded);
  });

  pendingTbody.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-gact]');
    if (btn) openWorkbench(Number(btn.dataset.id), 'pending');
  });
  gradedTbody.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-gact]');
    if (btn) openWorkbench(Number(btn.dataset.id), 'graded');
  });

  /* ================= 批改工作台 ================= */
  async function openWorkbench(id, fromTab) {
    returnTab = fromTab || 'pending';
    try {
      currentDetail = await API.getSubmission(id);
    } catch (e) {
      toast(e.message, 'error');
      return;
    }
    listPane.style.display = 'none';
    detailPane.style.display = 'none';
    gradingPane.style.display = '';
    renderWorkbench();
    window.scrollTo({ top: 0 });
  }

  function pickedLetters(response) {
    return (response || '').toUpperCase().split('').filter((c) => c >= 'A' && c <= 'Z');
  }

  function renderOptions(q) {
    const picked = new Set(pickedLetters(q.response));
    const refs = new Set(pickedLetters(q.reference_answer));
    return '<div class="grade-options">' + (q.options || []).map((o) => {
      const isPicked = picked.has(o.key);
      const isRef = refs.has(o.key);
      let cls = 'grade-option';
      let tag = '';
      if (isPicked && isRef) { cls += ' picked-correct'; tag = '<i class="go-flag ok">学生选对</i>'; }
      else if (isPicked && !isRef) { cls += ' picked-wrong'; tag = '<i class="go-flag no">学生错选</i>'; }
      else if (isRef) { cls += ' ref-only'; tag = '<i class="go-flag ref">正确答案</i>'; }
      return `<div class="${cls}"><span class="q-option-key">${o.key}</span><span>${escapeHtml(o.content)}</span>${tag}</div>`;
    }).join('') + '</div>';
  }

  function graderTag(q) {
    if (q.is_correct === null || q.is_correct === undefined) {
      return '<span class="grader-tag pending">待批改</span>';
    }
    if (q.grader === 'ai') {
      return `<span class="grader-tag ai">AI 判定：${q.is_correct === 1 ? '正确' : '错误'}</span>`;
    }
    return `<span class="grader-tag teacher">老师批改：${q.is_correct === 1 ? '正确' : '错误'}</span>`;
  }

  function renderQuestionCard(q) {
    const optionsHtml = CHOICE[q.type] ? renderOptions(q) : '';
    const isText = q.type === 'fill' || q.type === 'short';
    const responseHtml = q.response
      ? escapeHtml(q.response).replace(/\n/g, '<br>')
      : '<span class="resp-empty">（学生未作答）</span>';
    const correctChecked = q.is_correct === 1 ? 'checked' : '';
    const wrongChecked = (q.is_correct !== null && q.is_correct !== undefined && q.is_correct !== 1) ? 'checked' : '';
    const scoreVal = q.got_score === null || q.got_score === undefined ? '' : q.got_score;
    return `
      <div class="grade-card ${q.is_correct === null || q.is_correct === undefined ? 'is-pending' : ''}" data-answer="${q.answer_id}">
        <div class="question-head">
          <div class="question-title">
            <span class="q-seq">${q.seq}</span>
            <span class="qt-badge qt-${q.type}">${TYPE_LABELS[q.type] || q.type_label}</span>
            <span class="q-stem">${escapeHtml(q.stem)}</span>
            <span class="q-score-badge">满分 ${q.max_score}</span>
            ${graderTag(q)}
          </div>
        </div>
        ${optionsHtml}
        <div class="grade-resp">
          <div class="grade-resp-row">
            <span class="answer-label">学生作答</span>
            <div class="answer-content">${responseHtml}</div>
          </div>
          <div class="grade-resp-row">
            <span class="answer-label">参考答案</span>
            <div class="answer-content">${escapeHtml(q.reference_answer || '').replace(/\n/g, '<br>') || '<span class="resp-empty">（无）</span>'}</div>
          </div>
          ${q.reference_analysis ? `
          <div class="grade-resp-row">
            <span class="answer-label">解析要点</span>
            <div class="answer-content">${escapeHtml(q.reference_analysis).replace(/\n/g, '<br>')}</div>
          </div>` : ''}
          ${q.comment ? `
          <div class="grade-resp-row ${q.grader === 'ai' ? 'ai-comment' : ''}">
            <span class="answer-label">${q.grader === 'ai' ? 'AI 评语' : '评语'}</span>
            <div class="answer-content">${escapeHtml(q.comment).replace(/\n/g, '<br>')}</div>
          </div>` : ''}
        </div>
        <div class="grade-controls">
          <label class="grade-judge"><input type="radio" name="judge-${q.answer_id}" data-role="correct" value="1" ${correctChecked}> 判对</label>
          <label class="grade-judge wrong"><input type="radio" name="judge-${q.answer_id}" data-role="wrong" value="0" ${wrongChecked}> 判错</label>
          <label class="grade-score-input">得分
            <input type="number" min="0" max="${q.max_score}" step="1" data-role="score" value="${scoreVal}" placeholder="0-${q.max_score}">
            / ${q.max_score}
          </label>
          <input type="text" class="grade-comment-input" data-role="comment" maxlength="500"
                 value="${escapeHtml(q.comment || '')}" placeholder="评语（可选）">
        </div>
      </div>`;
  }

  function renderWorkbench() {
    const d = currentDetail;
    document.getElementById('grading-title').textContent =
      `${d.student_name} · ${d.assignment_title}`;
    const statusChip = d.status === 'pending'
      ? '<span class="grader-tag pending">待批改</span>'
      : '<span class="grader-tag teacher">已批改</span>';
    document.getElementById('grading-meta').innerHTML = `
      <span class="meta-chip">🎓 ${escapeHtml(d.student_name)}（${escapeHtml(d.student_no || '无学号')}）</span>
      <span class="meta-chip">📚 ${escapeHtml(d.course_name || '-')}</span>
      <span class="meta-chip">👥 ${escapeHtml(d.class_name || '-')}</span>
      <span class="meta-chip faint">提交于 ${fmtFull(d.submitted_at)}</span>
      ${statusChip}`;
    document.getElementById('grading-max').textContent = d.max_score;
    document.getElementById('grading-list').innerHTML = d.answers.map(renderQuestionCard).join('');
    updateLiveTotal();
  }

  function collectGrades() {
    const cards = document.querySelectorAll('#grading-list .grade-card');
    const grades = [];
    let pendingEmpty = 0;
    cards.forEach((card) => {
      const id = Number(card.dataset.answer);
      const scoreInput = card.querySelector('[data-role="score"]');
      const correct = card.querySelector('[data-role="correct"]').checked;
      const wrong = card.querySelector('[data-role="wrong"]').checked;
      const comment = card.querySelector('[data-role="comment"]').value.trim();
      const raw = scoreInput.value.trim();
      if (raw === '') {
        pendingEmpty += 1;
        return;
      }
      const score = Math.trunc(Number(raw));
      const max = Number(scoreInput.max);
      if (Number.isNaN(score) || score < 0 || score > max) {
        const err = new Error(`第 ${cards.length ? '' : ''}题得分需在 0-${max} 之间`);
        err.card = card;
        throw err;
      }
      let isCorrect = score > 0 ? 1 : 0;
      if (correct) isCorrect = 1;
      if (wrong) isCorrect = 0;
      grades.push({ answer_id: id, is_correct: isCorrect, score, comment });
    });
    return { grades, pendingEmpty };
  }

  function updateLiveTotal() {
    const cards = document.querySelectorAll('#grading-list .grade-card');
    let sum = 0;
    let pending = 0;
    cards.forEach((card) => {
      const v = card.querySelector('[data-role="score"]').value.trim();
      if (v === '') { pending += 1; return; }
      const n = Number(v);
      if (!Number.isNaN(n)) sum += n;
    });
    document.getElementById('grading-total').textContent = sum;
    document.getElementById('grading-total').classList.toggle('is-pending', pending > 0);
    document.getElementById('btn-save-grade').title = pending ? `还有 ${pending} 题未评分` : '';
  }

  document.getElementById('grading-list').addEventListener('input', updateLiveTotal);
  document.getElementById('grading-list').addEventListener('change', updateLiveTotal);

  document.getElementById('btn-save-grade').addEventListener('click', async () => {
    let collected;
    try {
      collected = collectGrades();
    } catch (e) {
      toast(e.message, 'error');
      if (e.card) e.card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    if (!collected.grades.length) {
      toast('请至少为一道题评分后再保存', 'error');
      return;
    }
    const btn = document.getElementById('btn-save-grade');
    btn.disabled = true;
    btn.textContent = '保存中…';
    try {
      const detail = await API.saveGrade(currentDetail.id, { grades: collected.grades });
      currentDetail = detail;
      renderWorkbench();
      refreshBadge();
      if (detail.status === 'graded') {
        toast('批改完成，已计入已批作业', 'success');
        setTimeout(() => openTab(returnTab), 600);
      } else {
        toast(`已保存，还有 ${collected.pendingEmpty} 题待批`, 'success');
      }
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '💾 保存批改';
    }
  });

  document.getElementById('btn-back-grading').addEventListener('click', () => {
    openTab(returnTab);
  });

  onViewShow('assignments', () => {
    refreshBadge();
    if (activeTab === 'pending') loadPending();
    if (activeTab === 'graded') loadGraded();
  });

  window.GradingPage = { openTab, refreshBadge, openWorkbench };
})();
