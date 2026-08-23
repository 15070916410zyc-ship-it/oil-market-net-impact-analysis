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

复制 `.env.example` 为 `.env.local` 后填写：

- `VITE_ANALYSIS_API_BASE_URL`：现有 Python 模型服务地址
- `VITE_SUPABASE_URL`：Lovable/Supabase 项目地址
- `VITE_SUPABASE_PUBLISHABLE_KEY`：浏览器可用的公开密钥

没有配置生产接口时，页面会明确显示“演示数据”，并使用固定种子的可复现数据。保存操作自动使用浏览器本地存储。

Supabase 已建立 `public.saved_records` 表并启用行级权限，只允许登录用户访问自己的记录。
