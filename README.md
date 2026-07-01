# InfoDigest

[![CI](https://github.com/xuess/info-digest/actions/workflows/ci.yml/badge.svg)](https://github.com/xuess/info-digest/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

轻量、零运维、可自托管的开源信息聚合器。基于 RSS 采集、规则评分、定时推送到飞书/钉钉。

## 架构

```
feeds.yaml 源注册表
      │
      ▼
collector (HTTP fetch + feedparser + 归一化 + 去重)
      │
      ▼
rater (规则评分: 权威/新鲜度/关键词/唯一性/热度)
      │
      ▼
storage (SQLite 持久化 + 增量)
      │
      ▼
formatter (Jinja2 模板排版)
      │
      ▼
delivery (飞书/钉钉 webhook, 分段限流)
```

## 特性

- **零 LLM 依赖** — 采集、去重、评级、排版、推送全链路确定性代码
- **五维规则评分** — 权威度 × 新鲜度 × 关键词 × 唯一性 × 热度，可配置权重
- **多通道推送** — 飞书 interactive card + 钉钉 markdown
- **增量采集** — ETag/Last-Modified，不重复抓取
- **GitHub Actions** — 定时调度，密钥走 Secrets，零运维
- **159 测试用例** — 全链路覆盖，覆盖率 ≥60%

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/xuess/info-digest.git
cd info-digest

# 安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 编辑配置
vim config/feeds.yaml    # 添加/修改 RSS 源
vim config/rater.yaml    # 调整评分权重和关键词

# 运行（仅采集，不推送）
python -m infodigest.cli collect

# 运行完整管道（采集 + 评分 + 推送）
FEISHU_WEBHOOK="https://..." python -m infodigest.cli run

# 查看运行统计
python -m infodigest.cli report
```

## 配置

### config/settings.yaml — 全局设置
```yaml
storage:
  db_path: data/infodigest.db
collector:
  timeout: 15
  retries: 3
delivery:
  feishu:
    enabled: true
    webhook_env: FEISHU_WEBHOOK
  dingtalk:
    enabled: false
```

### config/feeds.yaml — RSS 源注册表
```yaml
sources:
  - id: hackernews
    url: https://hnrss.org/frontpage
    category: tech
    authority: 0.9
    lang: en
    tags: [news, startup, ai]
    enabled: true
```

### config/rater.yaml — 评分配置
```yaml
weights: { authority: 30, freshness: 25, relevance: 25, uniqueness: 10, engagement: 10 }
keywords:
  ai: 1.0
  llm: 1.0
  rust: 0.7
grade_thresholds: { A: 75, B: 50 }
push_grade_min: B
```

## GitHub Actions 部署

1. Fork 本仓库
2. 在 Settings → Secrets and variables → Actions 添加：
   - `FEISHU_WEBHOOK` — 飞书机器人 webhook URL
   - `FEISHU_SECRET` — 飞书签名密钥（可选）
   - `DINGTALK_WEBHOOK` — 钉钉机器人 webhook URL
   - `DINGTALK_SECRET` — 钉钉签名密钥
3. Actions 自动运行：每日 9:00 和 17:00 北京时间
4. 也可手动触发：Actions → Digest → Run workflow

## 开发

```bash
pip install -r requirements.txt
pytest --cov=infodigest --cov-fail-under=60
ruff check infodigest/ tests/
```

### 目录结构

```
infodigest/
├── collector/     # 采集层 (fetcher/parser/normalizer/dedup)
├── rater/         # 评级层 (scorer)
├── storage/       # 存储层 (models/repo)
├── formatter/     # 排版层 (builder + Jinja2 模板)
├── delivery/      # 推送层 (feishu/dingtalk/limiter)
├── scheduler/     # 编排层 (runner)
└── cli.py         # 命令行入口
```

## 贡献

欢迎贡献 RSS 源！参见 [CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## License

MIT
