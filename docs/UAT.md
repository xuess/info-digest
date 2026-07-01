# UAT.md — 端到端验收剧本

## 场景 1：空库首次运行

**前提**：全新数据库，无历史数据

**步骤**：
```bash
# 清除旧数据
rm -f data/infodigest.db

# 运行完整管道（仅收集，不推送）
python -m infodigest.cli -v collect

# 检查数据库
sqlite3 data/infodigest.db "SELECT COUNT(*) FROM entries;"
sqlite3 data/infodigest.db "SELECT grade, COUNT(*) FROM entries GROUP BY grade;"
```

**预期**：
- entries 表有数据（取决于源可达性）
- 分级分布合理（A 级通常较少）

## 场景 2：重复运行幂等性

**步骤**：
```bash
python -m infodigest.cli collect
python -m infodigest.cli collect
```

**预期**：
- 第二次运行不产生重复条目
- `SELECT COUNT(*) FROM entries` 两次结果相同

## 场景 3：增量抓取

**步骤**：
```bash
# 第一次运行
python -m infodigest.cli collect
sqlite3 data/infodigest.db "SELECT id, etag IS NOT NULL FROM sources LIMIT 5;"

# 第二次运行（应大部分 304）
python -m infodigest.cli -v collect 2>&1 | grep "not modified"
```

**预期**：
- sources 表有 etag/last_modified 值
- 第二次运行大部分源返回 "not modified"

## 场景 4：评分与分级

**步骤**：
```bash
python -m infodigest.cli collect
sqlite3 data/infodigest.db "SELECT title, raw_score, grade FROM entries ORDER BY raw_score DESC LIMIT 10;"
```

**预期**：
- 分数在 0-100 范围内
- A 级条目分数 ≥75
- 高权威源 + 新鲜 + 关键词匹配的条目分数更高

## 场景 5：报告查看

**步骤**：
```bash
python -m infodigest.cli report
```

**预期**：
- 显示运行 ID、时间、采集/去重/评级/推送数量

## 场景 6：坏源降级

**步骤**：在 `feeds.yaml` 中添加一个不可达的源：
```yaml
  - id: bad-source
    url: https://nonexistent.example.com/feed.xml
    enabled: true
```

**预期**：
- 运行不崩溃
- 其他源正常采集
- `report` 显示 sources_failed > 0

## 场景 7：飞书推送（需配置 Webhook）

**前提**：设置环境变量 `FEISHU_WEBHOOK`

**步骤**：
```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
python -m infodigest.cli run
```

**预期**：
- 飞书群收到 interactive card 消息
- 消息包含条目标题、摘要、评分

## 验收清单

- [ ] 空库首次运行不崩溃
- [ ] 重复运行幂等
- [ ] 增量抓取生效（304）
- [ ] 评分在合理范围
- [ ] A/B/C 分级正确
- [ ] 报告命令可用
- [ ] 坏源不阻塞整体运行
- [ ] 飞书推送可达
