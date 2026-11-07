# Japan Shopping Buddy · PayPal 版（日淘搭子）

> PayPal AI Hackathon · **Agentic Commerce** 赛道参赛作品。
> 一个能**自主识别日本商品 → 跨平台比价 → 阶梯精算到手价 → 经 PayPal 安全完成跨境收款**的 AI Agent。
> 核心命题：Agent 能替用户发起并完成一笔跨境支付，但**永不自动扣款**——每笔都过人工确认卡点。

## 为什么是 Agentic Commerce

跨境购物的痛点不是"买不到"，而是链路断裂：看不懂日文、算不清真实到手价、代购层层加价、支付不放心。
本作品让 Agent 自主跑完「识别 → 比价 → 试算 → 发起支付」全链路，用 PayPal 沙箱 Orders 完成收款闭环，
同时用「Reviewer 卡点 + 永不自动 approve」证明：**自主决策与资金安全可以共存**。

## 设计亮点（吸收比价类 Skill 最佳实践 + 跨境升级）

> 对照 ClawHub 市售比价 Skill（同类最高仅 A/70 分）逐项升级，评委可复测验证：

1. **双模式诚实输出**：证据充足走 Mode 1 强结论；单一货源/无同款走 Mode 2——明说「为什么不下强结论、还有什么没验证」，绝不编价格凑数
2. **同款匹配置信度（高/中/低）**：近似款 ≠ 同款，比价结论必带置信度
3. **Caveats 防坑清单**：成色待核实 / 二手券后价陷阱 / 汇率时效 / 转运称重浮动 / 渠道覆盖，固定区块逐单提醒
4. **收货地第一变量**：非日元显示先反推原价（Amazon 按收货地自动换算 HKD），比价前必问收货地——直邮 vs 转运税差实测可达 ¥400
5. **安全卡点**：确认单 → 用户二次确认 → 沙箱 Orders 创建（≠扣款）→ 人工 approve → capture，全程凭证不入代码

## 收款闭环演示（沙箱）

```bash
export PAYPAL_CLIENT_ID=.. PAYPAL_CLIENT_SECRET=..
# 1. 创建订单（Agent 发起，intent=CAPTURE，JPY 计价）
python3 scripts/paypal_billing.py create-order --amount-jpy 16500 --item-name "LYCEE POD020-LYB"
#    → 返回 order_id + status=CREATED + approve 链接
# 2. 用户在沙箱 approve（人工卡点，Agent 绝不代点）
# 3. capture 收款（二次确认后执行）
```

安全边界：凭证只读环境变量；订单创建 ≠ 扣款；approve / capture 必须用户确认。

## 完整链路（Pipeline 模式）

1. **识别**：解析日本商品链接/截图，译出商品名/成色/价格（非日元显示自动反推日元原价，收货地必问）
2. **路由**：渠道路由决策树判断最优渠道（references/channel_routing.md）
3. **比价**：乐天 RWS 一手 API（scripts/rakuten_search.py）；Amazon 页面快照兜底（代理 + 浏览器 UA + `/-/en/` 路径突破反爬）；中古源（Mercari/雅虎拍卖/骏河屋）走代拍中转或预置参考价
4. **试算**：到手价 = 商品 + 日国内运费 + 转运 + 汇率折算 + 行邮税（scripts/arrival_price.py，标注估算 + 汇率快照时间戳）
5. **确认单**：按 assets/confirmation_template.md 生成 PayPal 支付确认单（Reviewer 卡点）
6. **支付**：用户二次确认后走沙箱 Orders 创建 → approve → capture 闭环

## 目录

- `SKILL.md` — Agent 指令（六步 SOP + Gotchas + 禁止行为 + 退出条件）
- `scripts/` — `rakuten_search.py`（乐天 RWS）、`exchange_rate.py`（汇率双源+缓存）、`arrival_price.py`（到手价试算）、`paypal_billing.py`（PayPal 沙箱 OAuth + Orders）
- `references/` — 渠道路由 / 到手价公式 / 转运价目 / 离线兜底快照 / PayPal API 文档
- `assets/` — 支付确认单模板（Generator）+ 图标
- `docs/demo-video-60s.md` — 参赛 Demo 视频 60 秒分镜脚本

## 实测记录（2026-11-06/07）

- 乐天 RWS 真实返回商品行情（非 Mock），如 ace GENE 背包 5 家店统一 ¥33,000
- Amazon 日本站页面快照突破反爬，解析出标题 + 主购买价（¥33,000 / 森贝儿 C-81 ¥3,827）
- PayPal 沙箱 create-order 成功（order_id + approve 链接，status=CREATED 未扣款）
- 汇率双源实时刷新（JPY→CNY 0.042214 @2026-11-07）

## 与华为小红书版的关系

本仓库为 **PayPal 赛专用版**（含收款闭环）。同一作品的**中立工具版**（无 PayPal，确认单→购买指引，不代收代付）见
[japan-shopping-buddy](https://github.com/dontcry/japan-shopping-buddy)（华为·小红书 Skill 创新赛参赛作品）。
两版共享识别/比价/试算能力，仅在支付环节分叉。

## 合规声明

- 沙箱凭证仅用于演示，勿用于真实交易；生产环境请轮换密钥。
- 作品使用 AI 辅助开发；商品价格/汇率/运费均为估算值，以实际成交为准。
