/**
 * 教学首页统计 + 班级 / 课程基础数据管理。
 * 同时通过 window.BasicData 向作业、生成模块提供班级/课程下拉数据。
 */
(function () {
  const { escapeHtml, fmtTime, fmtFull, openModal, closeModal, openConfirm, onViewShow } = window.AppUI;

  /* ---------- 班级/课程共享数据 ---------- */
  const BasicData = {
    classes: [],
    courses: [],
    async refresh() {
      const [cls, cou] = await Promise.all([API.listClasses(), API.listCourses()]);
      this.classes = cls;
      this.courses = cou;
    },
    fillSelect(selectEl, kind, allLabel) {
      const items = kind === 'class' ? this.classes : this.courses;
      const current = selectEl.value;
      selectEl.innerHTML =
        (allLabel ? `<option value="">${allLabel}</option>` : '') +
        items.map((it) => `<option value="${it.id}">${escapeHtml(it.name)}</option>`).join('');
      if (current) selectEl.value = current;
    },
  };
  window.BasicData = BasicData;

  /* ---------- 教学首页 ---------- */
  async function loadDashboard() {
    try {
      const data = await API.dashboard();
      document.getElementById('stat-classes').textContent = data.class_count;
      document.getElementById('stat-courses').textContent = data.course_count;
      document.getElementById('stat-assignments').textContent = data.assignment_count;
      document.getElementById('stat-questions').textContent = data.question_count;
      const tbody = document.getElementById('home-recent-tbody');
      if (!data.recent_assignments.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">暂无作业，去「作业习题」或「AI 生成作业」创建吧</td></tr>';
        return;
      }
      tbody.innerHTML = data.recent_assignments.map((a) => `
        <tr>
          <td><span class="cell-title">${escapeHtml(a.title)}</span></td>
          <td>${escapeHtml(a.class_name || '-')}</td>
          <td>${escapeHtml(a.course_name || '-')}</td>
          <td>${a.question_count}</td>
          <td>${sourceBadge(a.source)}</td>
          <td>${fmtTime(a.updated_at)}</td>
          <td><button class="link-btn" data-open="${a.id}">查看</button></td>
        </tr>`).join('');
    } catch (e) {
      toast(e.message, 'error');
    }
  }

  function sourceBadge(source) {
    return source === 'ai'
      ? '<span class="src-badge src-ai">✨ AI 生成</span>'
      : '<span class="src-badge src-manual">手动</span>';
  }
  window.sourceBadge = sourceBadge;

  document.getElementById('home-recent-tbody').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-open]');
    if (!btn) return;
    window.AppNav.switch('assignments');
    window.AssignmentsPage.openDetail(Number(btn.dataset.open));
  });
  document.getElementById('home-go-assignments').addEventListener('click', () => {
    window.AppNav.switch('assignments');
  });

  onViewShow('home', loadDashboard);

  /* ---------- 班级管理 ---------- */
  const classesTbody = document.getElementById('classes-tbody');

  async function loadClasses() {
    try {
      BasicData.classes = await API.listClasses();
    } catch (e) {
      toast(e.message, 'error');
      BasicData.classes = [];
    }
    renderClasses();
  }

  function renderClasses() {
    if (!BasicData.classes.length) {
      classesTbody.innerHTML = '<tr><td colspan="6" class="empty-cell">还没有班级，点击右上角「新增班级」创建</td></tr>';
      return;
    }
    classesTbody.innerHTML = BasicData.classes.map((c) => `
      <tr>
        <td>${c.id}</td>
        <td><span class="cell-title">${escapeHtml(c.name)}</span></td>
        <td>${escapeHtml(c.grade || '-')}</td>
        <td>${escapeHtml(c.remark || '-')}</td>
        <td>${fmtFull(c.created_at)}</td>
        <td>
          <button class="link-btn" data-act="edit" data-id="${c.id}">编辑</button>
          <button class="link-btn danger" data-act="delete" data-id="${c.id}">删除</button>
        </td>
      </tr>`).join('');
  }

  onViewShow('classes', loadClasses);
  document.getElementById('btn-add-class').addEventListener('click', () => openBasicModal('class'));

  classesTbody.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const item = BasicData.classes.find((c) => c.id === Number(btn.dataset.id));
    if (!item) return;
    if (btn.dataset.act === 'edit') openBasicModal('class', item);
    if (btn.dataset.act === 'delete') {
      const ok = await openConfirm('删除班级', `确定删除班级「${item.name}」吗？该班级下存在作业时无法删除。`);
      if (!ok) return;
      try {
        await API.deleteClass(item.id);
        await Promise.all([loadClasses(), BasicData.refresh()]);
        toast('班级已删除', 'success');
      } catch (err) { toast(err.message, 'error'); }
    }
  });

  /* ---------- 课程管理 ---------- */
  const coursesTbody = document.getElementById('courses-tbody');

  async function loadCourses() {
    try {
      BasicData.courses = await API.listCourses();
    } catch (e) {
      toast(e.message, 'error');
      BasicData.courses = [];
    }
    renderCourses();
  }

  function renderCourses() {
    if (!BasicData.courses.length) {
      coursesTbody.innerHTML = '<tr><td colspan="6" class="empty-cell">还没有课程，点击右上角「新增课程」创建</td></tr>';
      return;
    }
    coursesTbody.innerHTML = BasicData.courses.map((c) => `
      <tr>
        <td>${c.id}</td>
        <td><span class="cell-title">${escapeHtml(c.name)}</span></td>
        <td>${escapeHtml(c.major || '-')}</td>
        <td>${escapeHtml(c.remark || '-')}</td>
        <td>${fmtFull(c.created_at)}</td>
        <td>
          <button class="link-btn" data-act="edit" data-id="${c.id}">编辑</button>
          <button class="link-btn danger" data-act="delete" data-id="${c.id}">删除</button>
        </td>
      </tr>`).join('');
  }

  onViewShow('courses', loadCourses);
  document.getElementById('btn-add-course').addEventListener('click', () => openBasicModal('course'));

  coursesTbody.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const item = BasicData.courses.find((c) => c.id === Number(btn.dataset.id));
    if (!item) return;
    if (btn.dataset.act === 'edit') openBasicModal('course', item);
    if (btn.dataset.act === 'delete') {
      const ok = await openConfirm('删除课程', `确定删除课程「${item.name}」吗？该课程下存在作业时无法删除。`);
      if (!ok) return;
      try {
        await API.deleteCourse(item.id);
        await Promise.all([loadCourses(), BasicData.refresh()]);
        toast('课程已删除', 'success');
      } catch (err) { toast(err.message, 'error'); }
    }
  });

  /* ---------- 班级/课程通用弹窗 ---------- */
  const CONFIG = {
    class: {
      titleNew: '新增班级', titleEdit: '编辑班级',
      nameLabel: '班级名称', namePlaceholder: '例如：计科2301',
      extraLabel: '年级', extraPlaceholder: '例如：2023级',
      loader: loadClasses,
      create: API.createClass, update: API.updateClass,
    },
    course: {
      titleNew: '新增课程', titleEdit: '编辑课程',
      nameLabel: '课程名称', namePlaceholder: '例如：数据结构',
      extraLabel: '所属专业', extraPlaceholder: '例如：计算机科学与技术',
      loader: loadCourses,
      create: API.createCourse, update: API.updateCourse,
    },
  };
  let modalKind = null;

  function openBasicModal(kind, item) {
    modalKind = kind;
    const cfg = CONFIG[kind];
    document.getElementById('basic-modal-title').textContent = item ? cfg.titleEdit : cfg.titleNew;
    document.getElementById('basic-name-label').textContent = cfg.nameLabel;
    document.getElementById('basic-extra-label').textContent = cfg.extraLabel;
    document.getElementById('basic-name').value = item?.name || '';
    document.getElementById('basic-name').placeholder = cfg.namePlaceholder;
    document.getElementById('basic-extra').value = (kind === 'class' ? item?.grade : item?.major) || '';
    document.getElementById('basic-extra').placeholder = cfg.extraPlaceholder;
    document.getElementById('basic-remark').value = item?.remark || '';
    document.getElementById('basic-id').value = item?.id || '';
    openModal('basic-modal');
    setTimeout(() => document.getElementById('basic-name').focus(), 30);
  }

  document.getElementById('basic-cancel').addEventListener('click', () => closeModal('basic-modal'));
  document.getElementById('basic-save').addEventListener('click', async () => {
    const cfg = CONFIG[modalKind];
    const id = document.getElementById('basic-id').value;
    const name = document.getElementById('basic-name').value.trim();
    const extra = document.getElementById('basic-extra').value.trim();
    const remark = document.getElementById('basic-remark').value.trim();
    if (!name) { toast(`${cfg.nameLabel}不能为空`, 'error'); return; }
    const payload = {
      name, remark,
      ...(modalKind === 'class' ? { grade: extra } : { major: extra }),
    };
    try {
      if (id) await cfg.update(Number(id), payload);
      else await cfg.create(payload);
      closeModal('basic-modal');
      await Promise.all([cfg.loader(), BasicData.refresh()]);
      toast(id ? '已保存修改' : '创建成功', 'success');
    } catch (e) { toast(e.message, 'error'); }
  });

  /* 初始化基础数据（供后续模块下拉使用） */
  BasicData.refresh().catch(() => {});
})();
