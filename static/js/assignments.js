/**
 * 作业习题管理：筛选列表、作业详情在线查看、作业与题目的增删改查。
 */
(function () {
  const { escapeHtml, fmtTime, fmtFull, openModal, closeModal, openConfirm, onViewShow } = window.AppUI;

  const TYPE_LABELS = {
    single: '单选题', multiple: '多选题', judge: '判断题',
    fill: '填空题', short: '简答题',
  };
  const DIFF_LABELS = { 1: '简单', 2: '中等', 3: '困难' };

  const listPane = document.getElementById('assignment-list-pane');
  const detailPane = document.getElementById('assignment-detail-pane');
  const tbody = document.getElementById('assignments-tbody');

  let currentDetail = null;

  /* ================= 列表 ================= */
  async function loadAssignments() {
    await window.BasicData.refresh();
    window.BasicData.fillSelect(document.getElementById('filter-class'), 'class', '全部班级');
    window.BasicData.fillSelect(document.getElementById('filter-course'), 'course', '全部课程');
    const params = {};
    const classId = document.getElementById('filter-class').value;
    const courseId = document.getElementById('filter-course').value;
    const keyword = document.getElementById('filter-keyword').value.trim();
    if (classId) params.class_id = classId;
    if (courseId) params.course_id = courseId;
    if (keyword) params.keyword = keyword;
    try {
      const rows = await API.listAssignments(params);
      renderList(rows);
    } catch (e) {
      toast(e.message, 'error');
    }
  }

  function renderList(rows) {
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="9" class="empty-cell">没有符合条件的作业</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map((a) => `
      <tr>
        <td><span class="cell-title">${escapeHtml(a.title)}</span></td>
        <td>${escapeHtml(a.class_name || '-')}</td>
        <td>${escapeHtml(a.course_name || '-')}</td>
        <td><span class="diff-badge diff-${a.difficulty}">${DIFF_LABELS[a.difficulty] || '中等'}</span></td>
        <td>${a.question_count}</td>
        <td>
          <span class="sub-count-all">${a.submission_count || 0}</span>
          ${a.pending_count ? `<span class="sub-count-pending" title="待批数">/${a.pending_count} 待批</span>` : ''}
        </td>
        <td>${window.sourceBadge(a.source)}</td>
        <td>${fmtTime(a.updated_at)}</td>
        <td>
          <button class="link-btn" data-act="view" data-id="${a.id}">查看</button>
          <button class="link-btn" data-act="grade" data-id="${a.id}" data-title="${escapeHtml(a.title)}">批改</button>
          <button class="link-btn danger" data-act="delete" data-id="${a.id}">删除</button>
        </td>
      </tr>`).join('');
  }

  function showListPane() {
    detailPane.style.display = 'none';
    listPane.style.display = '';
  }
  function showDetailPane() {
    listPane.style.display = 'none';
    detailPane.style.display = '';
  }

  document.getElementById('btn-filter-search').addEventListener('click', loadAssignments);
  document.getElementById('filter-keyword').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') loadAssignments();
  });
  document.getElementById('btn-filter-reset').addEventListener('click', () => {
    document.getElementById('filter-class').value = '';
    document.getElementById('filter-course').value = '';
    document.getElementById('filter-keyword').value = '';
    loadAssignments();
  });
  document.getElementById('btn-back-assignments').addEventListener('click', () => {
    showListPane();
    loadAssignments();
  });

  tbody.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const id = Number(btn.dataset.id);
    if (btn.dataset.act === 'view') openDetail(id);
    if (btn.dataset.act === 'grade') {
      window.GradingPage.openTab('pending', { keyword: btn.dataset.title || '' });
    }
    if (btn.dataset.act === 'delete') {
      const ok = await openConfirm('删除作业', '删除后作业及其全部习题都不可恢复，确定删除吗？');
      if (!ok) return;
      try {
        await API.deleteAssignment(id);
        toast('作业已删除', 'success');
        loadAssignments();
      } catch (err) { toast(err.message, 'error'); }
    }
  });

  const gradingPane = document.getElementById('grading-pane');
  onViewShow('assignments', () => {
    if (gradingPane.style.display !== 'none') return;
    if (detailPane.style.display === 'none' || !currentDetail) {
      showListPane();
      loadAssignments();
    }
  });

  /* ================= 作业弹窗 ================= */
  function openAssignmentModal(item) {
    window.BasicData.fillSelect(document.getElementById('assignment-class'), 'class', '请选择班级');
    window.BasicData.fillSelect(document.getElementById('assignment-course'), 'course', '请选择课程');
    document.getElementById('assignment-modal-title').textContent = item ? '编辑作业' : '新建作业';
    document.getElementById('assignment-id').value = item?.id || '';
    document.getElementById('assignment-title').value = item?.title || '';
    document.getElementById('assignment-class').value = item?.class_id || '';
    document.getElementById('assignment-course').value = item?.course_id || '';
    document.getElementById('assignment-difficulty').value = item?.difficulty || 2;
    document.getElementById('assignment-requirement').value = item?.requirement || '';
    openModal('assignment-modal');
    setTimeout(() => document.getElementById('assignment-title').focus(), 30);
  }

  document.getElementById('btn-add-assignment').addEventListener('click', () => openAssignmentModal(null));
  document.getElementById('assignment-cancel').addEventListener('click', () => closeModal('assignment-modal'));
  document.getElementById('assignment-save').addEventListener('click', async () => {
    const id = document.getElementById('assignment-id').value;
    const payload = {
      title: document.getElementById('assignment-title').value.trim(),
      class_id: Number(document.getElementById('assignment-class').value),
      course_id: Number(document.getElementById('assignment-course').value),
      difficulty: Number(document.getElementById('assignment-difficulty').value),
      requirement: document.getElementById('assignment-requirement').value.trim(),
    };
    if (!payload.title) { toast('作业标题不能为空', 'error'); return; }
    if (!payload.class_id || !payload.course_id) { toast('请选择班级与课程', 'error'); return; }
    try {
      if (id) await API.updateAssignment(Number(id), payload);
      else await API.createAssignment(payload);
      closeModal('assignment-modal');
      toast(id ? '作业已更新' : '作业创建成功，可继续添加题目', 'success');
      if (id && currentDetail && currentDetail.id === Number(id)) {
        await openDetail(Number(id));
      } else if (!id) {
        // 创建后留在列表并刷新（用户可点查看后加题）
        showListPane();
        loadAssignments();
      }
    } catch (e) { toast(e.message, 'error'); }
  });

  document.getElementById('btn-edit-assignment').addEventListener('click', () => {
    if (currentDetail) openAssignmentModal(currentDetail);
  });
  document.getElementById('btn-delete-assignment').addEventListener('click', async () => {
    if (!currentDetail) return;
    const ok = await openConfirm('删除作业', `确定删除「${currentDetail.title}」及其全部习题吗？`);
    if (!ok) return;
    try {
      await API.deleteAssignment(currentDetail.id);
      toast('作业已删除', 'success');
      currentDetail = null;
      showListPane();
      loadAssignments();
    } catch (e) { toast(e.message, 'error'); }
  });

  /* ================= 作业详情 ================= */
  async function openDetail(id) {
    try {
      currentDetail = await API.getAssignment(id);
    } catch (e) {
      toast(e.message, 'error');
      return;
    }
    showDetailPane();
    renderDetail();
  }

  function renderDetail() {
    const a = currentDetail;
    document.getElementById('detail-title').textContent = a.title;
    document.getElementById('detail-meta').innerHTML = `
      <span class="meta-chip">👥 ${escapeHtml(a.class_name || '-')}</span>
      <span class="meta-chip">📚 ${escapeHtml(a.course_name || '-')}</span>
      <span class="diff-badge diff-${a.difficulty}">${DIFF_LABELS[a.difficulty] || '中等'}</span>
      ${window.sourceBadge(a.source)}
      <span class="meta-chip faint">更新于 ${fmtFull(a.updated_at)}</span>`;
    document.getElementById('detail-requirement').textContent =
      a.requirement ? `作业要求：${a.requirement}` : '';
    document.getElementById('detail-count').textContent = a.questions.length;
    const box = document.getElementById('question-list');
    if (!a.questions.length) {
      box.innerHTML = '<div class="empty-block">暂无题目，点击右上角「添加题目」或使用 AI 生成</div>';
      return;
    }
    box.innerHTML = a.questions.map(renderQuestionCard).join('');
  }

  function answerText(q) {
    if (q.type === 'single' || q.type === 'multiple' || q.type === 'judge') {
      const optMap = Object.fromEntries((q.options || []).map((o) => [o.key, o.content]));
      const letters = (q.answer || '').split('');
      return letters.map((k) => `${k}. ${optMap[k] || ''}`).join('　');
    }
    return escapeHtml(q.answer || '').replace(/\n/g, '<br>');
  }

  function renderQuestionCard(q) {
    let optionsHtml = '';
    if (q.options && q.options.length) {
      optionsHtml = '<div class="q-options">' + q.options.map((o) => `
        <div class="q-option ${q.answer.includes(o.key) ? 'is-correct' : ''}">
          <span class="q-option-key">${o.key}</span><span>${escapeHtml(o.content)}</span>
          ${q.answer.includes(o.key) ? '<i class="correct-flag">✓ 正确</i>' : ''}
        </div>`).join('') + '</div>';
    }
    const isTextAnswer = q.type === 'fill' || q.type === 'short';
    return `
      <div class="question-card" data-qid="${q.id}">
        <div class="question-head">
          <div class="question-title">
            <span class="q-seq">${q.seq}</span>
            <span class="qt-badge qt-${q.type}">${TYPE_LABELS[q.type]}</span>
            <span class="q-stem">${escapeHtml(q.stem)}</span>
            <span class="q-score-badge">${q.score ?? 5} 分</span>
          </div>
          <div class="question-ops">
            <button class="link-btn" data-qact="edit" data-qid="${q.id}">编辑</button>
            <button class="link-btn danger" data-qact="delete" data-qid="${q.id}">删除</button>
          </div>
        </div>
        ${optionsHtml}
        <details class="answer-fold">
          <summary>📖 查看参考答案与解析</summary>
          <div class="answer-body">
            <div class="answer-row ${isTextAnswer ? 'text-answer' : ''}">
              <span class="answer-label">参考答案</span>
              <div class="answer-content">${isTextAnswer ? answerText(q) : answerText(q)}</div>
            </div>
            ${q.analysis ? `
            <div class="answer-row">
              <span class="answer-label">解析</span>
              <div class="answer-content">${escapeHtml(q.analysis).replace(/\n/g, '<br>')}</div>
            </div>` : ''}
          </div>
        </details>
      </div>`;
  }

  document.getElementById('question-list').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-qact]');
    if (!btn || !currentDetail) return;
    const qid = Number(btn.dataset.qid);
    const q = currentDetail.questions.find((x) => x.id === qid);
    if (btn.dataset.qact === 'edit' && q) openQuestionModal(q);
    if (btn.dataset.qact === 'delete') {
      const ok = await openConfirm('删除题目', '确定删除这道题目吗？');
      if (!ok) return;
      try {
        await API.deleteQuestion(qid);
        toast('题目已删除', 'success');
        await openDetail(currentDetail.id);
      } catch (err) { toast(err.message, 'error'); }
    }
  });

  document.getElementById('btn-add-question').addEventListener('click', () => openQuestionModal(null));

  /* ================= 题目弹窗 ================= */
  const qTypeEl = document.getElementById('question-type');
  const qOptionsField = document.getElementById('question-options-field');
  const qOptionsBox = document.getElementById('question-options-box');
  const qAnswerField = document.getElementById('question-answer-field');
  const qAnswerLabel = document.getElementById('question-answer-label');
  const qAnswerEl = document.getElementById('question-answer');
  const btnAddOption = document.getElementById('btn-add-option');

  const CHOICE = { single: true, multiple: true, judge: true };

  function currentQType() { return qTypeEl.value; }

  /* 选项编辑区：judge 固定两项；single/multiple 可增删 */
  function renderOptionsEditor(options, answer) {
    const type = currentQType();
    const inputType = type === 'multiple' ? 'checkbox' : 'radio';
    const letters = (answer || '').split('');
    qOptionsBox.innerHTML = '';
    options.forEach((opt, idx) => {
      const row = document.createElement('div');
      row.className = 'opt-row';
      const fixed = type === 'judge';
      row.innerHTML = `
        <label class="opt-pick"><input type="${inputType}" name="q-correct" ${letters.includes(opt.key) ? 'checked' : ''} value="${opt.key}"></label>
        <span class="opt-key">${opt.key}</span>
        <input type="text" class="opt-content" maxlength="300" value="${escapeHtml(opt.content)}" ${fixed ? 'data-fixed="1"' : ''}>
        ${fixed ? '' : '<button type="button" class="opt-del link-btn danger" data-idx="' + idx + '">移除</button>'}`;
      qOptionsBox.appendChild(row);
    });
    btnAddOption.style.display = type === 'judge' ? 'none' : '';
  }

  function syncAnswerEditorVisibility() {
    const type = currentQType();
    if (CHOICE[type]) {
      qOptionsField.style.display = '';
      qAnswerField.style.display = 'none';
    } else {
      qOptionsField.style.display = 'none';
      qAnswerField.style.display = '';
      qAnswerLabel.textContent = type === 'fill' ? '参考答案（多空用分号分隔）' : '参考答案 / 评分要点';
    }
  }

  function rebuildByType(prevAnswer) {
    syncAnswerEditorVisibility();
    const type = currentQType();
    if (type === 'judge') {
      renderOptionsEditor([{ key: 'A', content: '正确' }, { key: 'B', content: '错误' }], prevAnswer || 'A');
    } else if (CHOICE[type]) {
      renderOptionsEditor([
        { key: 'A', content: '' }, { key: 'B', content: '' },
        { key: 'C', content: '' }, { key: 'D', content: '' },
      ], prevAnswer || '');
    }
  }

  qTypeEl.addEventListener('change', () => rebuildByType(''));

  btnAddOption.addEventListener('click', () => {
    const rows = qOptionsBox.querySelectorAll('.opt-row');
    if (rows.length >= 8) { toast('每题最多 8 个选项', 'error'); return; }
    const key = String.fromCharCode(65 + rows.length);
    const row = document.createElement('div');
    row.className = 'opt-row';
    row.innerHTML = `
      <label class="opt-pick"><input type="${currentQType() === 'multiple' ? 'checkbox' : 'radio'}" name="q-correct" value="${key}"></label>
      <span class="opt-key">${key}</span>
      <input type="text" class="opt-content" maxlength="300" value="">
      <button type="button" class="opt-del link-btn danger">移除</button>`;
    qOptionsBox.appendChild(row);
  });

  qOptionsBox.addEventListener('click', (e) => {
    if (!e.target.classList.contains('opt-del')) return;
    const rows = qOptionsBox.querySelectorAll('.opt-row');
    if (rows.length <= 2) { toast('选择题至少保留 2 个选项', 'error'); return; }
    e.target.closest('.opt-row').remove();
    // 重新编号
    qOptionsBox.querySelectorAll('.opt-row').forEach((row, idx) => {
      const key = String.fromCharCode(65 + idx);
      row.querySelector('.opt-key').textContent = key;
      const pick = row.querySelector('.opt-pick input');
      pick.value = key;
    });
  });

  function openQuestionModal(q) {
    document.getElementById('question-modal-title').textContent = q ? '编辑题目' : '添加题目';
    document.getElementById('question-id').value = q?.id || '';
    qTypeEl.value = q?.type || 'single';
    document.getElementById('question-stem').value = q?.stem || '';
    document.getElementById('question-score').value = q?.score ?? 5;
    document.getElementById('question-answer').value = (!CHOICE[q?.type] && q) ? q.answer : '';
    document.getElementById('question-analysis').value = q?.analysis || '';
    if (q && CHOICE[q.type]) {
      renderOptionsEditor(
        q.options && q.options.length
          ? q.options
          : [{ key: 'A', content: '' }, { key: 'B', content: '' }],
        q.answer
      );
    } else {
      rebuildByType('');
    }
    syncAnswerEditorVisibility();
    openModal('question-modal');
  }

  document.getElementById('question-cancel').addEventListener('click', () => closeModal('question-modal'));
  document.getElementById('question-save').addEventListener('click', async () => {
    if (!currentDetail) return;
    const qid = document.getElementById('question-id').value;
    const type = currentQType();
    const payload = {
      type,
      stem: document.getElementById('question-stem').value.trim(),
      analysis: document.getElementById('question-analysis').value.trim(),
      score: Math.trunc(Number(document.getElementById('question-score').value)) || 5,
    };
    if (payload.score < 1 || payload.score > 100) {
      toast('本题分值需在 1-100 之间', 'error'); return;
    }
    if (!payload.stem) { toast('题干不能为空', 'error'); return; }

    if (CHOICE[type]) {
      const rows = [...qOptionsBox.querySelectorAll('.opt-row')];
      const options = rows.map((row, idx) => ({
        key: String.fromCharCode(65 + idx),
        content: row.querySelector('.opt-content').value.trim(),
      }));
      if (options.some((o) => !o.content)) { toast('请填写全部选项内容', 'error'); return; }
      const picked = rows
        .filter((row) => row.querySelector('.opt-pick input').checked)
        .map((row) => row.querySelector('.opt-pick input').value);
      if (!picked.length) { toast('请勾选正确答案', 'error'); return; }
      if (type === 'single' && picked.length > 1) { toast('单选题只能有一个正确答案', 'error'); return; }
      payload.options = options;
      payload.answer = picked.join('');
    } else {
      payload.answer = qAnswerEl.value.trim();
      if (!payload.answer) { toast('参考答案不能为空', 'error'); return; }
    }

    try {
      if (qid) await API.updateQuestion(Number(qid), payload);
      else await API.addQuestion(currentDetail.id, payload);
      closeModal('question-modal');
      toast(qid ? '题目已更新' : '题目已添加', 'success');
      await openDetail(currentDetail.id);
    } catch (e) { toast(e.message, 'error'); }
  });

  window.AssignmentsPage = { openDetail };
})();
