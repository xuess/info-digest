# InfoDigest

轻量、零运维、可自托管的开源信息聚合器。基于 RSS 采集、规则评分、定时推送到飞书/钉钉。

## 特性

- **零 LLM 依赖** — 采集、去重、评级、排版、推送全链路确定性代码
- **规则评分** — 五维评分（权威/新鲜度/关键词/唯一性/热度），可配置权重
- **多通道推送** — 飞书 interactive card + 钉钉 markdown，分段限流
- **增量采集** — ETag/Last-Modified，不重复抓取
- **GitHub Actions 部署** — 定时调度，密钥走 Secrets

## 快速开始

```bash
pip install -r requirements.txt
# 编辑 config/feeds.yaml 添加你的 RSS 源
# 编辑 config/rater.yaml 调整评分权重和关键词
python -m infodigest.cli run
```

## 配置

- `config/settings.yaml` — 全局设置（调度/存储/推送通道开关）
- `config/feeds.yaml` — RSS 源注册表
- `config/rater.yaml` — 评分权重、关键词、阈值

## GitHub Actions 部署

1. Fork 本仓库
2. 在 Settings → Secrets 配置：`FEISHU_WEBHOOK`、`DINGTALK_WEBHOOK` 等
3. Actions 会按 cron 自动运行（每日 9:00/17:00 北京时间）

## 开发

```bash
pip install -r requirements.txt
pytest --cov=infodigest
```

## License

MIT
