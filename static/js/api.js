/**
 * API 封装：Axios 统一请求 + SSE 流式请求 + 全局 Toast。
 * 两个页面（index / chat）共用。
 */
(function () {
  const http = axios.create({ timeout: 30000 });

  http.interceptors.response.use(
    (resp) => {
      const body = resp.data;
      if (body.code !== 0) {
        const err = new Error(body.message || '请求失败');
        err.code = body.code;
        throw err;
      }
      return body.data;
    },
    (error) => {
      const b = error.response && error.response.data;
      const err = new Error((b && b.message) || '网络异常，请检查服务是否可用');
      err.code = b && b.code;
      err.data = b && b.data;
      return Promise.reject(err);
    }
  );

  const API = {
    // 会话
    listConversations: () => http.get('/api/conversations'),
    createConversation: (title) => http.post('/api/conversations', { title: title ?? null }),
    getConversation: (id) => http.get(`/api/conversations/${id}`),
    renameConversation: (id, title) => http.patch(`/api/conversations/${id}`, { title }),
    pinConversation: (id, pinned) => http.patch(`/api/conversations/${id}/pin`, { pinned }),
    deleteConversation: (id) => http.delete(`/api/conversations/${id}`),
    // 消息
    getMessages: (id) => http.get(`/api/conversations/${id}/messages`),
    // 教学：班级 / 课程
    listClasses: () => http.get('/api/classes'),
    createClass: (payload) => http.post('/api/classes', payload),
    updateClass: (id, payload) => http.put(`/api/classes/${id}`, payload),
    deleteClass: (id) => http.delete(`/api/classes/${id}`),
    listCourses: () => http.get('/api/courses'),
    createCourse: (payload) => http.post('/api/courses', payload),
    updateCourse: (id, payload) => http.put(`/api/courses/${id}`, payload),
    deleteCourse: (id) => http.delete(`/api/courses/${id}`),
    // 教学：首页统计
    dashboard: () => http.get('/api/dashboard'),
    // 教学：作业 / 习题
    listAssignments: (params) => http.get('/api/assignments', { params }),
    createAssignment: (payload) => http.post('/api/assignments', payload),
    getAssignment: (id) => http.get(`/api/assignments/${id}`),
    updateAssignment: (id, payload) => http.put(`/api/assignments/${id}`, payload),
    deleteAssignment: (id) => http.delete(`/api/assignments/${id}`),
    addQuestion: (assignmentId, payload) =>
      http.post(`/api/assignments/${assignmentId}/questions`, payload),
    updateQuestion: (id, payload) => http.put(`/api/questions/${id}`, payload),
    deleteQuestion: (id) => http.delete(`/api/questions/${id}`),
    // AI 生成
    generateAssignment: (payload) => http.post('/api/generate-assignment', payload),
    // 学生端（免登录作答）
    studentListAssignments: () => http.get('/api/student/assignments'),
    getPaper: (assignmentId) => http.get(`/api/student/assignments/${assignmentId}/paper`),
    submitAssignment: (assignmentId, payload) =>
      http.post(`/api/student/assignments/${assignmentId}/submit`, payload, { timeout: 120000 }),
    // 教师端批改
    gradingPendingCount: () => http.get('/api/grading/pending-count'),
    gradingList: (params) => http.get('/api/grading/submissions', { params }),
    getSubmission: (id) => http.get(`/api/grading/submissions/${id}`),
    saveGrade: (id, payload) => http.post(`/api/grading/submissions/${id}/grade`, payload),
  };

  /**
   * SSE 流式发送消息。
   * handlers: { meta, thinking, delta, error, done }
   *  - thinking: 深度思考模型的推理片段（实时展示，不落库）
   * deepThinking=true 时请求模型深度思考模式
   * 返回 AbortController，调用 abort() 可停止接收。
   */
  function sendMessageStream(conversationId, content, handlers, deepThinking = false) {
    const controller = new AbortController();

    (async () => {
      let resp;
      try {
        resp = await fetch(`/api/conversations/${conversationId}/messages/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
          body: JSON.stringify({ content, deep_thinking: !!deepThinking }),
          signal: controller.signal,
        });
      } catch (e) {
        if (e.name !== 'AbortError') handlers.error && handlers.error({ code: -1, message: '无法连接服务器' });
        return;
      }
      if (!resp.ok || !resp.body) {
        handlers.error && handlers.error({ code: resp.status, message: `服务异常（HTTP ${resp.status}）` });
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      const dispatch = (rawEvent) => {
        let event = 'message';
        const lines = rawEvent.split('\n');
        for (const line of lines) {
          if (line.startsWith('event:')) event = line.slice(6).trim();
        }
        const dataLine = lines.find((l) => l.startsWith('data:'));
        if (!dataLine) return;
        let data;
        try {
          data = JSON.parse(dataLine.slice(5).trim());
        } catch (_e) {
          data = {};
        }
        const fn = handlers[event];
        if (fn) fn(data);
      };

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let sep;
          while ((sep = buffer.indexOf('\n\n')) >= 0) {
            dispatch(buffer.slice(0, sep));
            buffer = buffer.slice(sep + 2);
          }
        }
        if (buffer.trim()) dispatch(buffer);
      } catch (e) {
        if (e.name !== 'AbortError') {
          handlers.error && handlers.error({ code: -1, message: '读取回复流失败：' + e.message });
        }
      }
    })();

    return controller;
  }

  /* ---------- 全局 Toast ---------- */
  function toast(message, type) {
    let box = document.getElementById('toast-box');
    if (!box) {
      box = document.createElement('div');
      box.id = 'toast-box';
      document.body.appendChild(box);
    }
    const el = document.createElement('div');
    el.className = 'toast ' + (type || 'info');
    el.textContent = message;
    box.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 250);
    }, 3200);
  }

  window.API = API;
  window.sendMessageStream = sendMessageStream;
  window.toast = toast;
})();
