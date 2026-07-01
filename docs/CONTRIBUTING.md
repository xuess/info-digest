# CONTRIBUTING.md — 贡献指南

## 如何贡献 RSS 源

1. Fork 本仓库
2. 编辑 `config/feeds.yaml`，添加新源：
   ```yaml
   - id: your-source-id        # 唯一标识，小写+连字符
     url: https://example.com/feed  # RSS/Atom URL
     category: tech              # tech/ai/security/opensource/product/blockchain
     authority: 0.5              # 0-1，初值建议 0.5
     lang: en                    # en/zh
     tags: [tag1, tag2]          # 相关标签
     enabled: false              # 新源默认 false，验证后改为 true
   ```
3. 运行 `python -m infodigest.cli collect` 验证源可达且解析正常
4. 确认无误后将 `enabled` 改为 `true`
5. 提交 PR，标题格式：`feat: add RSS source <source-name>`

## 源质量要求

- 必须是公开可访问的 RSS/Atom feed
- 内容应有持续更新（最近 30 天有新条目）
- 不接受纯广告/营销内容源
- authority 值参考同类源设定

## 开发流程

1. Clone 仓库并安装依赖：
   ```bash
   git clone https://github.com/xuess/info-digest.git
   cd info-digest
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. 创建功能分支：`git checkout -b feat/your-feature`

3. 编写代码 + 测试，确保：
   ```bash
   pytest --cov=infodigest --cov-fail-under=60
   ruff check infodigest/ tests/
   ```

4. 提交信息格式：`feat: 描述` / `fix: 描述` / `docs: 描述`

5. 提交 PR

## 代码规范

- Python 3.11+ 语法
- 使用 type hints
- 每个模块需有对应测试文件
- 不引入 LLM 依赖
- 配置走 YAML，不硬编码
