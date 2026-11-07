# PayPal AI Hackathon · Demo 视频 60 秒叙事脚本

> 用途：PayPal 赛题「Agentic Commerce」提交视频的核心叙事（可扩到 <3 分钟）。
> 定位：把「日淘搭子」三点竞争力（Agentic 完整度 / 场景真实度 / 安全可信）串成一条 60 秒可拍的分镜。
> 建议：横屏 16:9；旁白中文，关键术语配英文字幕（评委多为英文）。

## 分镜表

| # | 时间 | 画面 | 旁白（中文） | 英文字幕关键词 |
|---|---|---|---|---|
| 1 | 0:00–0:06 | 钩子：手机里一个日本娃娃商品页（LYCEE ¥16,500），AI 气泡弹出「要我帮你算到手价吗？」 | 海淘最烦什么？看不懂日文、算不清运费，还被代购加了价。 | Cross-border shopping is broken. |
| 2 | 0:06–0:18 | Agent 自主拆解：识别商品 → 调乐天 API 比价 → 拉实时汇率，数据跳动 | 我把这活交给一个 AI Agent——它自己读懂商品、调真实 API 比价、拉实时汇率。 | The agent reads, compares, quotes — autonomously. |
| 3 | 0:18–0:32 | 分项到手价面板：商品 + 转运 + 关税 + 汇率折算 → 总额精确到元 | 不是编个价，是一笔笔算：商品、转运、关税、汇率，到手价精确到元。 | Every cost item — real data, transparent. |
| 4 | 0:32–0:45 | 安全卡点：弹出「生成支付确认单？」→ 用户确认 → PayPal 沙箱 Orders「创建→capture」成功动画 | 但让它碰钱，最怕乱扣。所以每笔都强制二次确认，才用 PayPal 沙箱走完 Orders 的创建到收款。 | Human-in-the-loop. The agent never auto-charges. |
| 5 | 0:45–0:55 | 收束：一个「能自主决策、又不乱扣钱」的跨境支付 Agent，落标题 | 一个能自主决策、又不乱扣钱的跨境购物 Agent。 | A trustworthy Agentic Commerce assistant. |
| 6 | 0:55–0:60 | CTA：开源仓库 + PayPal 沙箱 | 代码全开源，支付接 PayPal——这就是 Agentic Commerce。 | Open source. Built on PayPal. |

## 三点竞争力的画面落点

1. **Agentic 完整度** → 分镜 2：强调「Agent 自己读懂 → 决策 → 比价」的自主链，而非人点按钮。
2. **场景真实度** → 分镜 3：真实商品（LYCEE ¥16,500）+ 真实乐天 API + 真实汇率 + 真实转运价目，分项透明。
3. **安全可信** → 分镜 4：Reviewer 二次确认 + 永不自动 approve + 沙箱 capture 闭环，把「自主」与「不乱扣钱」这对矛盾解掉。

## 拍摄/呈现要点

- 全程屏录 + 少量关键 UI 特写即可，无需真人出镜。
- 分镜 3 的「分项到手价」是信息密度最高的一幕，给足 14 秒并配一屏大字。
- 分镜 4 的「二次确认」要有明显的点击→确认交互，让评委看到人机卡点真实存在。
- 结尾 CTA 放 GitHub 地址 + PayPal 沙箱标识，点名开源与支付归属。