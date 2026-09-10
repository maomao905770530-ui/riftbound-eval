# riftbound-eval

符文战场（Riftbound）LLM 局部决策评测 —— 科研项目仓库。

从第一天起，所有代码、数据、结果都放这里。它未来就是你论文的开源资产。

## 目录结构

```
riftbound-eval/
├── 01_hello_llm.py        # 第一个 LLM 调用脚本（阶段 0 毕业作业）
├── env_check.py           # 环境自检
├── data/cards/            # 卡牌文本 JSON（阶段 2 填充真实数据）
├── results/               # 实验结果（自动生成，已 gitignore）
└── docs/                  # 笔记、精读文献笔记
```

## 快速开始（阶段 0）

```bash
# 1. 环境自检
python env_check.py

# 2. 离线演练（不花钱，验证流程）
python 01_hello_llm.py --mock

# 3. 正式调用：注册 https://platform.deepseek.com ，充值几块钱，
#    创建 API Key，然后设置环境变量后运行：
#    PowerShell:  $env:DEEPSEEK_API_KEY="sk-你的key"
python 01_hello_llm.py
```

跑通第 3 步 = **阶段 0 毕业**。

## 安全提醒

- API Key 只放环境变量，绝不写进代码、绝不提交到 Git（.gitignore 已排除 `.env`）。
- Key 泄露 = 别人拿你的钱跑模型。

## 当前进度

- [ ] 阶段 0：基础环境（第 1–2 周）
- [ ] 阶段 1：读文献建地图（第 1–3 周）
- [ ] 阶段 2：评测集构建（第 3–6 周）
- [ ] 阶段 3：跑实验（第 6–9 周）
- [ ] 阶段 4：写作投稿（第 9–14 周）
