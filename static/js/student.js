/**
 * 学生免登录作答页：选作业 → 填姓名学号 → 作答 → 提交看结果。
 */
(function () {
  const TYPE_LABELS = {
    single: '单选题', multiple: '多选题', judge: '判断题',
    fill: '填空题', short: '简答题',
  };

  const stepList = document.getElementById('step-list');
  const stepPaper = document.getElementById('step-paper');
  const stepResult = document.getElementById('step-result');
  const cardsBox = document.getElementById('assignment-cards');

  let paper = null;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function showStep(step) {
    stepList.style.display = step === 'list' ? '' : 'none';
    stepPaper.style.display = step === 'paper' ? '' : 'none';
    stepResult.style.display = step === 'result' ? '' : 'none';
    window.scrollTo({ top: 0 });
  }

  /* ---------- 作业列表 ---------- */
  async function loadAssignments() {
    cardsBox.innerHTML = '<div class="student-loading">作业加载中…</div>';
    try {
      const rows = await API.studentListAssignments();
      const usable = rows.filter((r) => r.question_count > 0);
      if (!usable.length) {
        cardsBox.innerHTML = '<div class="student-loading">老师暂未发布可作答的作业</div>';
        return;
      }
      cardsBox.innerHTML = usable.map((a) => `
        <div class="assignment-card" data-id="${a.id}">
          <div class="assignment-card-main">
            <div class="assignment-card-title">${esc(a.title)}</div>
            <div class="assignment-card-meta">
              <span>👥 ${esc(a.class_name || '未分班')}</span>
              <span>📚 ${esc(a.course_name || '-')}</span>
              <span>📄 共 ${a.question_count} 题</span>
            </div>
          </div>
          <button class="btn-primary btn-sm" data-id="${a.id}">开始作答 →</button>
        </div>`).join('');
    } catch (e) {
      cardsBox.innerHTML = `<div class="student-loading">加载失败：${esc(e.message)}</div>`;
    }
  }

  cardsBox.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-id]');
    if (btn) openPaper(Number(btn.dataset.id));
  });

  /* ---------- 试卷 ---------- */
  async function openPaper(id) {
    try {
      paper = await API.getPaper(id);
    } catch (e) {
      toast(e.message, 'error');
      return;
    }
    document.getElementById('paper-title').textContent = paper.title;
    document.getElementById('paper-meta').innerHTML = `
      <span>👥 ${esc(paper.class_name || '未分班')}</span>
      <span>📚 ${esc(paper.course_name || '-')}</span>
      <span>📄 共 ${paper.questions.length} 题 · 满分 ${paper.max_score} 分</span>`;
    document.getElementById('stu-name').value = '';
    document.getElementById('stu-no').value = '';
    document.getElementById('paper-questions').innerHTML = paper.questions.map(renderQuestion).join('');
    showStep('paper');
  }

  function renderQuestion(q) {
    let body = '';
    if (q.type === 'single' || q.type === 'judge') {
      body = '<div class="paper-options">' + (q.options || []).map((o) => `
        <label class="paper-option">
          <input type="radio" name="q-${q.id}" value="${o.key}">
          <span class="q-option-key">${o.key}</span><span>${esc(o.content)}</span>
        </label>`).join('') + '</div>';
    } else if (q.type === 'multiple') {
      body = '<div class="paper-options">' + (q.options || []).map((o) => `
        <label class="paper-option">
          <input type="checkbox" name="q-${q.id}" value="${o.key}">
          <span class="q-option-key">${o.key}</span><span>${esc(o.content)}</span>
        </label>`).join('') + '</div>';
    } else if (q.type === 'fill') {
      body = `<textarea class="paper-textarea" name="q-${q.id}" rows="2"
        placeholder="请按顺序填写各空，多个空用分号（；）分隔"></textarea>`;
    } else {
      body = `<textarea class="paper-textarea" name="q-${q.id}" rows="5"
        placeholder="请认真作答，本题由老师批改"></textarea>`;
    }
    return `
      <div class="question-card" data-qid="${q.id}">
        <div class="question-head">
          <div class="question-title">
            <span class="q-seq">${q.seq}</span>
            <span class="qt-badge qt-${q.type}">${TYPE_LABELS[q.type] || q.type_label}</span>
            <span class="q-stem">${esc(q.stem)}</span>
            <span class="q-score-badge">${q.score} 分</span>
          </div>
        </div>
        ${body}
      </div>`;
  }

  document.getElementById('btn-back-list').addEventListener('click', () => {
    paper = null;
    showStep('list');
    loadAssignments();
  });

  function collectAnswers() {
    const answers = [];
    for (const q of paper.questions) {
      let response = '';
      if (q.type === 'single' || q.type === 'judge') {
        const picked = document.querySelector(`input[name="q-${q.id}"]:checked`);
        response = picked ? picked.value : '';
      } else if (q.type === 'multiple') {
        response = [...document.querySelectorAll(`input[name="q-${q.id}"]:checked`)]
          .map((el) => el.value).join('');
      } else {
        const el = document.querySelector(`textarea[name="q-${q.id}"]`);
        response = el ? el.value.trim() : '';
      }
      answers.push({ question_id: q.id, response });
    }
    return answers;
  }

  document.getElementById('btn-submit-paper').addEventListener('click', async () => {
    const name = document.getElementById('stu-name').value.trim();
    const no = document.getElementById('stu-no').value.trim();
    if (!name) { toast('请填写姓名', 'error'); return; }
    if (!no) { toast('请填写学号', 'error'); return; }
    const answers = collectAnswers();
    const unanswered = paper.questions.filter((_, i) => !answers[i].response).length;
    if (unanswered > 0 && !window.confirm(`还有 ${unanswered} 道题未作答，确定提交吗？`)) return;

    const btn = document.getElementById('btn-submit-paper');
    btn.disabled = true;
    btn.textContent = '提交中，AI 正在批改客观题，请稍候…';
    try {
      const res = await API.submitAssignment(paper.id, {
        student_name: name, student_no: no, answers,
      });
      renderResult(res, name);
      showStep('result');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '✅ 提交作业';
    }
  });

  function renderResult(res, name) {
    const box = document.getElementById('result-card');
    if (res.status === 'graded') {
      box.innerHTML = `
        <div class="result-emoji">🎉</div>
        <div class="result-title">${esc(name)}，作业已提交并完成批改</div>
        <div class="result-score"><b>${res.total_score}</b><span> / ${res.max_score} 分</span></div>
        <div class="result-tip">本次作业全部为客观题，得分由系统即时判定</div>`;
    } else {
      box.innerHTML = `
        <div class="result-emoji">✅</div>
        <div class="result-title">${esc(name)}，作业提交成功</div>
        <div class="result-score partial"><b>${res.total_score}</b><span> / ${res.max_score} 分</span></div>
        <div class="result-tip">
          客观题（选择 / 判断 / 填空）已由 AI 即时判分，当前得分 <b>${res.total_score}</b> 分；<br>
          主观题（简答）等待老师批改，最终成绩以老师批完为准。
        </div>`;
    }
  }

  document.getElementById('btn-result-back').addEventListener('click', () => {
    paper = null;
    showStep('list');
    loadAssignments();
  });

  loadAssignments();
})();
