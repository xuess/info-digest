# DESIGN.md — 关键设计决策

## ADR-001: 不使用 LLM

**决策**：全链路使用确定性代码，不调用任何大语言模型。

**理由**：
- 可预测性：规则评分结果完全可复现
- 成本：零 API 调用费用
- 隐私：内容不离开本机
- 可维护性：评分规则可审计、可版本化

**权衡**：牺牲了语义理解能力，关键词匹配可能遗漏相关但用词不同的内容。

## ADR-002: SQLite 作为存储

**决策**：使用 SQLite 而非 PostgreSQL/MySQL。

**理由**：
- 零运维：无需额外服务
- GitHub Actions 友好：文件级存储
- 单用户场景无并发问题
- WAL 模式支持读写并发

**权衡**：不适合多实例共享数据。

## ADR-003: Jinja2 模板排版

**决策**：使用 Jinja2 模板构建推送内容，而非代码拼接。

**理由**：
- 模板与逻辑分离
- 非开发者可修改模板
- 支持多种输出格式（card JSON / markdown）

## ADR-004: feedparser 选型

**决策**：使用 feedparser 解析 RSS/Atom。

**理由**：
- 成熟库，20+ 年维护
- 支持 RSS 2.0 / Atom 1.0 / RDF
- 内置 struct_time 解析

## ADR-005: httpx 替代 requests

**决策**：使用 httpx 而非 requests。

**理由**：
- 同步 + 异步双模式（未来扩展）
- 原生 timeout 和 redirect 控制
- 更现代的 API

## 依赖选型

| 包 | 用途 | 版本 | 许可证 |
|---|---|---|---|
| feedparser | RSS 解析 | ≥6.0 | BSD-2 |
| httpx | HTTP 客户端 | ≥0.27 | BSD-3 |
| beautifulsoup4 | HTML 清洗 | ≥4.12 | MIT |
| lxml | HTML 解析器 | ≥5.0 | BSD |
| jinja2 | 模板引擎 | ≥3.1 | BSD-3 |
| pyyaml | YAML 解析 | ≥6.0 | MIT |
| pytest | 测试框架 | ≥8.0 | MIT |
| pytest-cov | 覆盖率 | ≥5.0 | MIT |

## 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| RSS 源失效 | 采集减少 | 源健康度监控，自动降权 |
| Webhook 限流 | 推送延迟 | 令牌桶限流 + 失败落盘重试 |
| feedparser 解析错误 | 条目丢失 | 异常捕获 + 日志，坏源不阻塞 |
| 标题党/低质内容 | 推送质量差 | 关键词降噪规则 + 人工调参 |
