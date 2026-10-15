/**
 * AI 生成作业：班级/课程/题型数量表单 → 调用生成接口 → 跳转作业详情校对。
 */
(function () {
  const { escapeHtml, onViewShow } = window.AppUI;
  const classEl = document.getElementById('gen-class');
  const courseEl = document.getElementById('gen-course');
  const numberInputs = [...document.querySelectorAll('.qtype-pill input[type=number]')];
  const totalEl = document.getElementById('gen-total');
  const btn = document.getElementById('btn-generate');

  function calcTotal() {
    const total = numberInputs.reduce((sum, el) => sum + (Number(el.value) || 0), 0);
    totalEl.textContent = total;
    totalEl.classList.toggle('over', total > 30);
    return total;
  }
  numberInputs.forEach((el) => el.addEventListener('input', calcTotal));

  async function prepareForm() {
    await window.BasicData.refresh();
    window.BasicData.fillSelect(classEl, 'class', '请选择班级');
    window.BasicData.fillSelect(courseEl, 'course', '请选择课程');
  }
  onViewShow('generate', prepareForm);
  prepareForm();

  btn.addEventListener('click', async () => {
    const classId = Number(classEl.value);
    const courseId = Number(courseEl.value);
    if (!classId || !courseId) { toast('请选择班级与专业课程', 'error'); return; }
    const counts = {};
    numberInputs.forEach((el) => { counts[el.dataset.qtype] = Number(el.value) || 0; });
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    if (total === 0) { toast('请至少为一种题型填写数量', 'error'); return; }
    if (total > 30) { toast('单次生成总数不能超过 30 题', 'error'); return; }

    const payload = {
      class_id: classId,
      course_id: courseId,
      title: document.getElementById('gen-title').value.trim(),
      difficulty: Number(document.getElementById('gen-difficulty').value),
      requirement: document.getElementById('gen-requirement').value.trim(),
      counts,
    };

    btn.disabled = true;
    const oldHtml = btn.innerHTML;
    btn.innerHTML = '<span class="gen-spinner"></span> AI 正在命题，请稍候…';
    try {
      const result = await API.generateAssignment(payload);
      toast(`生成完成：共 ${result.question_count} 道习题${result.dropped_count ? `，${result.dropped_count} 道不合规已丢弃` : ''}`, 'success');
      window.AppNav.switch('assignments');
      await window.AssignmentsPage.openDetail(result.assignment_id);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = oldHtml;
    }
  });
})();
