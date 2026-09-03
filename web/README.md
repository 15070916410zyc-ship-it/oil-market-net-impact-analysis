# 油价智析研究与决策前端

React + TypeScript 前端与同源 Python/Node API 组成一套可部署到 Vercel 的油价研究系统。页面不生成演示数据：来源或模型失败时显示错误状态，不用随机数或静态图冒充实时结果。

## 本地运行

```powershell
cd web
npm install
npm run dev
```

默认地址：`http://localhost:4173`。

## 页面

- `/`：动态入口页
- `/decision`：决策模式，包含影响因素、概率预测、风险预警、详细采购套保测算与行动建议
- `/professional`：专业模式，包含净影响、价格预测和危机预警
- `/data`：独立数据中心，包含变量因素查询、Perspective 数据表、金融产品查询与变量池

## 数据连接

Vercel 同时部署静态前端和同源服务端接口：

- `/api/health`：服务状态与数据源配置状态
- `/api/catalog`：FRED、EIA、GPRD 与 Yahoo 补充目录的统一搜索
- `/api/series`：FRED 官方 API，缺少密钥时使用 FRED 官方 CSV 作为降级来源
- `/api/instruments`：期货、期权及跨资产金融产品目录与可用行情
- `/api/models`：真实 VMD、滚动验证、格兰杰筛选、VAR-FEVD、HHT、结构断点与风险计算

`FRED_API_KEY` 与 `EIA_API_KEY` 必须配置为 Vercel 的 Sensitive Environment Variables。密钥不会进入浏览器、GitHub 仓库或前端构建产物，因此页面不提供密钥输入框。

首页 Brent/WTI、数据中心、专业模式和决策模式均使用线上接口。净影响流程只允许通过主模态格兰杰显著性门槛的变量进入 FEVD；主模态由本次计算自动选择一个或两个 IMF，FEVD `h` 由主模态事件期最高点与最低点间的交易日数自动确定。保存操作当前使用浏览器本地存储。

## 交互与计算组件

- ECharts：所有研究图、概率区间、结构断点、组合成本与多腿损益图，支持框选缩放、滚轮/拖动和导出图片。
- Perspective：在数据中心将真实序列切换为可排序、可检查的数据表。
- 本地 AI 解释：用户主动开启后才下载 WebLLM。普通桌面设备使用 Qwen3-1.7B Q4，内存不少于 12 GB 的桌面设备可使用 Qwen3-4B Q4；无 WebGPU、移动端或内存过低时不加载。提示词只接收带方法、日期和来源的数据包。
- 套保组合：包含期限梯、牛市价差、领口、日历、蝶式、海鸥式、鹰式、对角与多资产覆盖等结构；逐腿披露产品、方向、数量、到期月、行权价、权利金、保证金、费用、融资成本和压力情景。跨资产风险预算设有单品种上限。
- 统计诊断：价格预测显示 MAE、RMSE、方向准确率和区间覆盖率，并基于真实训练样本显示累计变化、年化变化、波动、Sharpe、最大回撤、VaR 与 CVaR；这些不是未来收益承诺。

## 验证

```powershell
cd web
npm run test
npm run test:e2e
npm run build

cd ..
.\.venv\Scripts\python.exe -m pytest -q
```

浏览器测试覆盖中英文、无缝模式切换、参数步进、格兰杰到 FEVD 门控、14 套多腿/多资产组合、数据中心搜索、变量加入与删除、桌面和移动端溢出检查。
