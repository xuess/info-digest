# DATA_MODEL.md — SQLite 数据模型

## 表结构

### sources — RSS 源注册表
```sql
CREATE TABLE sources (
    id TEXT PRIMARY KEY,           -- 唯一标识 (slug)
    url TEXT NOT NULL UNIQUE,      -- RSS Feed URL
    category TEXT,                 -- 分类 (tech/ai/security/opensource)
    lang TEXT,                     -- 语言 (en/zh)
    authority REAL DEFAULT 0.5,    -- 权威度 (0-1, 人工初值)
    tags TEXT,                     -- JSON 数组
    etag TEXT,                     -- HTTP ETag (增量抓取)
    last_modified TEXT,            -- HTTP Last-Modified
    enabled INTEGER DEFAULT 1,     -- 是否启用
    created_at TEXT DEFAULT (datetime('now'))
);
```

### entries — 文章条目
```sql
CREATE TABLE entries (
    uid TEXT PRIMARY KEY,          -- sha1(norm_title + domain)
    source_id TEXT,                -- 关联 sources.id
    title TEXT,                    -- 原始标题
    summary TEXT,                  -- 清洗后摘要 (纯文本, ≤500字)
    link TEXT,                     -- 原文链接
    published TEXT,                -- ISO8601 发布时间
    raw_score REAL,                -- 评分 (0-100)
    grade TEXT,                    -- A/B/C 分级
    engagement INTEGER,            -- 热度指标 (可选)
    digest_id TEXT,                -- 所属推送批次
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_entries_published ON entries(published);
CREATE INDEX idx_entries_grade ON entries(grade);
CREATE INDEX idx_entries_source_id ON entries(source_id);
```

### digests — 推送批次
```sql
CREATE TABLE digests (
    id TEXT PRIMARY KEY,           -- ULID 或 UUID
    created_at TEXT DEFAULT (datetime('now')),
    channel TEXT,                  -- 推送通道 (feishu/dingtalk)
    entry_count INTEGER,           -- 条目数
    status TEXT,                   -- sent/failed/partial
    error TEXT                     -- 错误信息 (可选)
);
```

### runs — 运行记录
```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    ended_at TEXT,
    collected INTEGER DEFAULT 0,   -- 采集条目数
    deduped INTEGER DEFAULT 0,     -- 去重后条目数
    rated INTEGER DEFAULT 0,       -- 评分级条目数
    delivered INTEGER DEFAULT 0,   -- 推送条目数
    status TEXT                    -- success/partial/failed
);
```

## 关系

```
sources (1) ──< entries (N)
digests (1) ──< entries (N)  [通过 digest_id]
runs 独立记录每次运行
```

## 设计决策

- **uid = sha1(norm_title + domain)**：标题+域名组合的哈希作为主键，保证同一来源的同标题文章不重复。
- **summary 存纯文本**：HTML 在入库前已清洗，存储空间小，查询简单。
- **grade 在评分后写入**：评分是独立步骤，结果回写 entries 表。
- **runs 表记录历史**：支持 `cli.py report` 查询近 7 天运行统计。
