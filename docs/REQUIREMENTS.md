# REQUIREMENTS.md — InfoDigest 需求清单

## 用户故事

1. **作为技术从业者**，我希望每天收到一份精选技术资讯推送，以便保持对行业趋势的了解，而无需主动浏览多个网站。
2. **作为团队管理者**，我希望通过飞书/钉钉群机器人自动推送信息摘要，以便团队成员在工作流中获取资讯。
3. **作为自托管用户**，我希望系统零运维，通过 GitHub Actions 自动运行，配置简单，不依赖外部服务。

## 功能清单 (MoSCoW)

### Must Have
| ID | 功能 | 验收标准 |
|---|---|---|
| F1 | RSS 源注册表 | `feeds.yaml` 定义 ≥8 源，每源含 id/url/category/authority/lang/tags/enabled |
| F2 | HTTP 增量抓取 | ETag/Last-Modified 命中时返回 304 跳过；5xx 重试 3 次 |
| F3 | Feed 解析 | 支持 RSS 2.0 / Atom 1.0 / RDF；缺字段降级不崩溃 |
| F4 | 去重 | sha1 主键去重 + 标题 Jaccard ≥0.8 二次去重 |
| F5 | 规则评分 | 五维评分 (0-100)，A/B/C 分级，纯函数无 IO |
| F6 | SQLite 存储 | entries/sources/digests/runs 四表，幂等 upsert |
| F7 | Jinja2 排版 | 飞书 card JSON + 钉钉 markdown，无 LLM |
| F8 | 飞书推送 | interactive card webhook，重试 3 次 |
| F9 | 钉钉推送 | markdown + HMAC-SHA256 签名 |
| F10 | GitHub Actions | ci.yml (测试) + digest.yml (定时推送) |
| F11 | CLI | `run`/`collect`/`report` 子命令 |

### Should Have
| ID | 功能 | 验收标准 |
|---|---|---|
| F12 | 分段推送 | 单消息 >30KB 或条目 >20 时分批 |
| F13 | 限流 | 飞书 5/min、钉钉 20/min 令牌桶 |
| F14 | 失败落盘 | webhook 失败写 `data/failed_digests/` 待重试 |
| F15 | OPML 导入 | OPML → feeds.yaml，新增源默认 disabled |
| F16 | 配置可调 | 权重/关键词/阈值全走 YAML，无硬编码 |

### Could Have
| ID | 功能 |
|---|---|
| F17 | 源健康度自动降权 |
| F18 | 多模板（每日/每周/分类） |
| F19 | 运行统计报表 |

### Won't Have (本版本)
- LLM 内容处理
- Web UI
- 用户认证

## 非功能需求

- **性能**：单次运行 <5 分钟（8 源）
- **可用性**：GitHub Actions 99% 可用
- **安全**：密钥只走 GitHub Secrets，不入仓库
- **可观测**：STATUS.md 实时状态，runs 表记录每次运行指标
