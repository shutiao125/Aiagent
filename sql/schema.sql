-- AI 辅助教学系统初始化脚本（MySQL 8.x，utf8mb4）
-- 容器首次启动时由 MySQL 镜像自动执行；应用启动时亦会幂等建表。

CREATE DATABASE IF NOT EXISTS ai_assistant
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai_assistant;

-- 移除旧版禁忌规则功能
DROP TABLE IF EXISTS forbidden_rules;

-- ========== AI 答疑对话（保留原有功能） ==========

-- 会话表
CREATE TABLE IF NOT EXISTS conversations (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title         VARCHAR(100)    NOT NULL DEFAULT '新会话',
  pinned        TINYINT(1)      NOT NULL DEFAULT 0,
  is_deleted    TINYINT(1)      NOT NULL DEFAULT 0,
  last_preview  VARCHAR(200)    NOT NULL DEFAULT '',
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_list (is_deleted, pinned, updated_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
  COMMENT = '答疑会话表';

-- 消息表（status/blocked_rule 为旧版遗留字段，新逻辑恒为 normal）
CREATE TABLE IF NOT EXISTS messages (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  conversation_id  BIGINT UNSIGNED NOT NULL,
  role             VARCHAR(20)     NOT NULL COMMENT 'user / assistant / system',
  content          MEDIUMTEXT      NOT NULL,
  status           VARCHAR(20)     NOT NULL DEFAULT 'normal',
  blocked_rule     VARCHAR(100)    NOT NULL DEFAULT '',
  is_deleted       TINYINT(1)      NOT NULL DEFAULT 0,
  created_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_conv_time (conversation_id, id, is_deleted)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
  COMMENT = '聊天消息表';

-- ========== 教学基础数据 ==========

-- 班级表
CREATE TABLE IF NOT EXISTS classes (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(50)     NOT NULL COMMENT '班级名称，如 计科2301',
  grade       VARCHAR(20)     NOT NULL DEFAULT '' COMMENT '年级，如 2023级',
  remark      VARCHAR(200)    NOT NULL DEFAULT '',
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_class_name (name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
  COMMENT = '班级表';

-- 专业课程表
CREATE TABLE IF NOT EXISTS courses (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(80)     NOT NULL COMMENT '课程名称，如 数据结构',
  major       VARCHAR(80)     NOT NULL DEFAULT '' COMMENT '开课专业，如 计算机科学与技术',
  remark      VARCHAR(200)    NOT NULL DEFAULT '',
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_course_name (name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
  COMMENT = '专业课程表';

-- 作业表
CREATE TABLE IF NOT EXISTS assignments (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title        VARCHAR(150)    NOT NULL COMMENT '作业标题',
  class_id     BIGINT UNSIGNED NOT NULL,
  course_id    BIGINT UNSIGNED NOT NULL,
  difficulty   TINYINT         NOT NULL DEFAULT 2 COMMENT '难度：1=易 2=中 3=难',
  requirement  TEXT            NULL COMMENT '知识点与出题要求',
  source       VARCHAR(10)     NOT NULL DEFAULT 'manual' COMMENT 'ai / manual',
  status       VARCHAR(12)     NOT NULL DEFAULT 'published' COMMENT 'draft / published',
  is_deleted   TINYINT(1)      NOT NULL DEFAULT 0,
  created_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_assign_list (is_deleted, class_id, course_id, updated_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
  COMMENT = '作业表';

-- 习题表
CREATE TABLE IF NOT EXISTS questions (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  assignment_id   BIGINT UNSIGNED NOT NULL,
  seq             INT             NOT NULL DEFAULT 1 COMMENT '题号',
  type            VARCHAR(12)     NOT NULL COMMENT 'single/multiple/judge/fill/short',
  stem            TEXT            NOT NULL COMMENT '题干',
  options_json    JSON            NULL COMMENT '选项：[{"key":"A","content":"..."}]',
  answer          MEDIUMTEXT      NOT NULL COMMENT '参考答案：单选 A，多选 AC，判断 A(正确)/B(错误)，填空/简答为文本',
  analysis        TEXT            NULL COMMENT '解析 / 评分要点',
  score           INT             NOT NULL DEFAULT 5 COMMENT '本题分值',
  created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_q_assign (assignment_id, seq)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
  COMMENT = '作业习题表';

-- ========== 学生作业提交与批改 ==========

-- 学生提交表（免登录提交，学号在同一作业内唯一）
CREATE TABLE IF NOT EXISTS submissions (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  assignment_id  BIGINT UNSIGNED NOT NULL,
  student_name   VARCHAR(50)     NOT NULL COMMENT '学生姓名',
  student_no     VARCHAR(30)     NOT NULL DEFAULT '' COMMENT '学号',
  status         VARCHAR(12)     NOT NULL DEFAULT 'pending' COMMENT 'pending=待批 / graded=已批',
  total_score    INT             NOT NULL DEFAULT 0 COMMENT '总得分',
  max_score      INT             NOT NULL DEFAULT 0 COMMENT '作业满分',
  submitted_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  graded_at      DATETIME        NULL,
  created_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_assign_student (assignment_id, student_no),
  KEY idx_sub_status (status, submitted_at),
  KEY idx_sub_assign (assignment_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
  COMMENT = '学生作业提交表';

-- 作答明细表（is_correct：NULL=未批 / 0=错误 / 1=正确）
CREATE TABLE IF NOT EXISTS submission_answers (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  submission_id  BIGINT UNSIGNED NOT NULL,
  question_id    BIGINT UNSIGNED NOT NULL,
  seq            INT             NOT NULL,
  type           VARCHAR(12)     NOT NULL COMMENT 'single/multiple/judge/fill/short',
  response       MEDIUMTEXT      NOT NULL COMMENT '学生作答：选择/判断存字母，填空/简答为文本',
  is_correct     TINYINT(1)      NULL,
  score          INT             NULL COMMENT '本题得分，未批为 NULL',
  grader         VARCHAR(10)     NOT NULL DEFAULT '' COMMENT 'ai / teacher',
  comment        TEXT            NULL COMMENT 'AI 评语或教师评语',
  graded_at      DATETIME        NULL,
  created_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_sa_sub (submission_id, seq)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
  COMMENT = '提交作答明细表';
