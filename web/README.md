# 油价智析原生前端

这是与现有 Streamlit/Python 分析层并行的 React + TypeScript 前端，可直接导入 Lovable 或部署到任意 Vite 静态托管平台。

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
- `/professional`：专业模式，包含净影响、价格预测、危机预警和数据中心

## 数据连接

Vercel 同时部署静态前端和同源服务端接口：

- `/api/health`：服务状态与数据源配置状态
- `/api/catalog`：受控的官方数据目录
- `/api/series`：FRED 官方 API，缺少密钥时使用 FRED 官方 CSV 作为降级来源

`FRED_API_KEY` 与 `EIA_API_KEY` 必须配置为 Vercel 的 Sensitive Environment Variables。密钥不会进入浏览器、GitHub 仓库或前端构建产物，因此页面不提供密钥输入框。

首页 Brent 最新值、价格历史和专业模式的数据中心使用线上接口；净影响和危机风险模块仍清楚标记为研究基准结果。保存操作当前使用浏览器本地存储。
