# PayPal AI Hackathon · Demo 视频 2 分钟叙事脚本

> 用途：Devpost 提交视频正式分镜（规则：仅前 3 分钟被评审，本片 2:00 留足余量）。
> 定位：把三点竞争力（Agentic 完整度 / 场景真实度 / 安全可信）串成一条 120 秒可拍分镜，核心差异点是**真实跑通的 PayPal 沙箱闭环**。
> 建议：横屏 16:9；旁白中文，关键术语配英文字幕（评委多为英文）；全程屏录，无需真人出镜。
> 拍摄素材清单见文末。

## 分镜表

| # | 时间 | 画面 | 旁白（中文） | 英文字幕关键词 |
|---|---|---|---|---|
| 1 | 0:00–0:10 | 钩子：乐天搜索结果页 `https://search.rakuten.co.jp/search/mall/Lycee-%E6%B5%B4%E8%A1%A3/`（110 件、满屏日文 + 日元价 + 送料），AI 气泡弹出「要我帮你算到手价吗？」（原商品详情页 `child-kansai/10017747` 已下架，会跳转店铺首页，故改用搜索页） | 海淘日本最烦什么？看不懂日文、算不清运费关税，代购还层层加价。 | Cross-border shopping from Japan is broken. |
| 2 | 0:10–0:30 | 屏录终端：先 `source demo-env.sh`（画面只见 `<已导出>`，无明文密钥）→ `rakuten_search.py "Lycee 浴衣" --hits 5` 返回 `status=current` 的真实行情：¥2,640（にんじゃがKIDS）/ ¥2,200（子供服かんさい楽天市場店）/ ¥1,980×3（Rakuten Fashion×2、NARUMIYA ONLINE），每家带 itemCode 与抓取时间 → 切到无凭证窗口，同一条命令显示 `status=unavailable / AUTH_MISSING` + 【MOCK样例】标注 | 我把这活交给一个 AI Agent。它自己调乐天一手 API 比价——搜同一件 LYCEE 浴衣，五家店从 ¥1,980 报到 ¥2,640，谁便宜它不替你下结论，只把每家的价格、店名、商品编号和抓取时间一起摊开。数据不可用时，它明说「暂不可用」，绝不编个价格凑数。 | The agent pulls live Rakuten listings and shows the spread — ¥1,980 to ¥2,640 across five shops, each with shop name, item code and fetch time. When data is unavailable, it says so. No fake data. |
| 3 | 0:30–0:55 | 到手价确认单特写：商品 + 国内运费 + 转运 + 关税 + 汇率快照，分项到元；滚动展示目的地矩阵（us 免税额内 0 税 / sg GST 9% / eu IOSS / hk 自由港 / other 未建模） | 到手价不是猜的：商品、转运、关税、汇率快照，一笔笔列清，每行都带计算依据和数据来源。换收货地，税制跟着换——美国 800 美元免税额、新加坡 9% GST、欧盟 IOSS，没建模的税种直接标注「需按当地另计」，不编数字。 | Every line: basis + source. Destination-aware, never fabricated. |
| 4 | 0:55–1:40 | **核心段落**：支付确认单弹出 → 用户点击确认 → 终端 `create-order` 返回 `status=CREATED`（大字幕：此刻未扣款）→ 切浏览器 PayPal 沙箱 approve 页人工点击 → `get-order` 显示 `APPROVED` → `capture-order` 返回 `COMPLETED + capture_id=8GY16250C6388210U` → 再跑一次 capture，返回 `already_captured=true（幂等，未重复扣款）` | 让 Agent 碰钱，最怕乱扣。所以支付三道闸：第一，订单创建不等于扣款——看，CREATED 状态下钱包没动；第二，approve 必须你本人到 PayPal 点确认，Agent 不代点；第三，capture 之后我故意再跑一次——看，幂等保护，绝不重复扣款。整个过程顺序号和凭证全部可回查。 | create ≠ charge. approve = human click. capture = idempotent. |
| 5 | 1:40–1:52 | 快闪回顾：六步流水线图（识别→路由→比价→试算→确认→支付）+ 「永不自动扣款」大字 | 识别、比价、试算、确认、支付——一个完整跑通的 Agentic Commerce 闭环。它最诚实的输出，有时是「在这儿买不划算」。 | A complete, honest Agentic Commerce loop. |
| 6 | 1:52–2:00 | CTA 收束：GitHub 仓库地址 + PayPal 沙箱标识 + 标题落版 | 代码全开源，支付接 PayPal Orders——这就是 Japan Shopping Buddy。 | Open source. Built on PayPal. |

## 三点竞争力的画面落点

1. **Agentic 完整度** → 分镜 2 + 5：强调「Agent 自己读懂 → 决策 → 比价 → 发起支付」的自主链，且六步流水线可视化。
2. **场景真实度** → 分镜 2 + 3：真实商品（LYCEE ¥16,500）、真实乐天 API、真实汇率快照、真实转运价目，`AUTH_MISSING` 降级场景也照实拍。
3. **安全可信** → 分镜 4（占全片 1/3 时长）：三道闸逐一演示，幂等二次 capture 是其他队伍最难复刻的证据。

## 拍摄/呈现要点

- 屏录为主：终端（深色主题、字号调大）+ 浏览器（沙箱 approve 页）+ 确认单 Markdown 渲染。
- 分镜 3 确认单给足 25 秒，每行停留可读；`basis + source` 列滚动特写。
- 分镜 4 的三个状态变化（CREATED → APPROVED → COMPLETED）每处都加角标时间戳，暗示全程可审计。
- 幂等验证是「意想不到的细节」，旁白语气可稍夸张（"我故意再跑一次"）。
- 结尾落版：`github.com/dontcry/japan-shopping-buddy-paypal` + PayPal 沙箱 logo。

## 拍摄素材清单（开录前备齐）

- [ ] 终端：`arrival_price.py --quote` 生成确认单（LYCEE ¥16,500，cn 收货）
- [ ] 终端：`rakuten_search.py "Lycee 浴衣" --hits 5` 有凭证（`status=current`，¥1,980~¥2,640 五店价差）+ 无凭证（AUTH_MISSING + MOCK 标注）各录一条
- [ ] 终端：`create-order` → `get-order` → `capture-order` ×2（沙箱凭证注入，勿录进画面：凭证行打码或用 `export` 后省略）
- [ ] 浏览器：沙箱买家 approve 全过程（登录 → 同意 → 回跳）
- [ ] 到手价目的地矩阵：us / sg / eu / hk / other 五条命令输出截图
- [ ] 安全提示：沙箱凭证与 capture_id 出现画面时确认无真实账户信息；视频公开前复核一遍

## 提交链路提醒

录制 → 上传 YouTube（公开或不列出，≤3 分钟）→ 回 Devpost 编辑页把视频字段从占位链接 `demo-video-pending` 换成真实 URL → Submit 页勾选条款 → Submit project（截止 2026-11-13 04:00 GMT+8）。

## 英文配音稿（旁白 + 烧字幕统一用这份）

> 决策：Devpost 为英文评审，**旁白改英文**，字幕同为英文（静音浏览也能读）。全稿 279 词 / 120 秒 ≈ 140 wpm，正常解说语速，无需赶。中文列保留仅作拍摄参考，不再用于成片。

| 镜 | 时间 | 英文旁白 |
|---|---|---|
| 1 | 0:00–0:10 | Shopping from Japan is brutal. The page is in Japanese, shipping and duty are a mystery, and resellers stack their markup on top. |
| 2 | 0:10–0:30 | So I hand this to an agent. It calls Rakuten's own API and pulls five live listings for the same yukata — ¥1,980 to ¥2,640 — each with shop name, item code, and the exact fetch time. It doesn't pick a winner for you. And when credentials are missing, it prints "unavailable" — never a made-up price. |
| 3 | 0:30–0:55 | Landed cost, line by line: item, domestic leg, forwarding, duty, and the FX snapshot with its timestamp. Change the destination and the tax model changes with it — the US $800 de minimis, Singapore's 9% GST, the EU's IOSS. Anything we haven't modelled is marked "calculate locally". No invented numbers. |
| 4 | 0:55–1:40 | Letting an agent touch money means three gates. Gate one: creating an order is not charging. Status CREATED — the wallet hasn't moved. Gate two: approval happens in PayPal, by you, in the browser. The agent never clicks on your behalf. Gate three: I capture — COMPLETED, here's the capture id. Now I run capture again, on purpose. `already_captured` is true. Idempotent — no double charge. Every id in this sequence is queryable afterwards. |
| 5 | 1:40–1:52 | Identify, route, compare, calculate, confirm, pay — one complete agentic commerce loop. And sometimes the most honest answer it gives me is: don't buy it here. |
| 6 | 1:52–2:00 | Open source on GitHub, payments on PayPal Orders. This is Japan Shopping Buddy. |

### 配音要点

- 数字念法：`¥1,980` → "one thousand nine hundred eighty yen"；`$800` → "eight hundred dollars"；`9% GST` → "nine percent G S T"；`IOSS` → "EE-oss"（或直接拼读 "I O S S"，全片保持一致）
- 镜 4 的 `already_captured` 不要念变量名，说 "already captured is true"；`CREATED` / `COMPLETED` 按 PayPal 官方读法重读即可
- 每镜句尾留 0.3~0.5 秒气口，方便对齐切点
