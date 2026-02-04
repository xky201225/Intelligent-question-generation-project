# 智能组卷系统 V3

## 目录结构

- backend/：Flask REST API（MySQL + AI + 导入导出）
- frontend/：Vue3 + Element Plus（业务页面）
- docs/：接口与策略规范（后续补齐）

## 后端启动

```bash
cd backend
python -m pip install -r requirements.txt
python run.py
```

默认 API 地址：`http://localhost:5000/api`

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认通过 `VITE_API_BASE_URL` 连接后端，未配置时使用 `http://localhost:5000/api`。
