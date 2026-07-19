# 🚀 快速模式设置 (Cloudflare Tunnel)

你电脑当后端服务器，OCR 识别速度 2-4 秒（比免费云服务快 10 倍）。

## 第一次设置（10 分钟，只需做一次）

### 1. 安装 Python 依赖

```bash
cd promoter-performance-tracker/backend
pip install -r requirements.txt
```

### 2. 下载 cloudflared

从 https://github.com/cloudflare/cloudflared/releases/latest 下载
- Windows: `cloudflared-windows-amd64.exe`
- Mac: `cloudflared-darwin-amd64`

放到你的用户目录下（`C:\Users\你的用户名\cloudflared.exe` 或 `~/cloudflared`）

### 3. 创建 .env 文件

在 `backend/` 目录下创建 `.env`：
```
CLOUD_DEPLOY=true
```

---

## 每次要快速模式时（2 步）

### 步骤 1：启动后端

打开终端，运行：
```bash
cd promoter-performance-tracker/backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 步骤 2：启动 Tunnel

打开另一个终端，运行：

**Windows:**
```bash
%USERPROFILE%\cloudflared.exe tunnel --url http://localhost:8000
```

**Mac:**
```bash
~/cloudflared tunnel --url http://localhost:8000
```

会显示一个网址，类似：
```
https://xxxx-xxxx.trycloudflare.com
```

### 步骤 3：更新前端

把上一步的网址填到 `frontend/public/_redirects`：
```
/api/*      https://xxxx-xxxx.trycloudflare.com/api/:splat  200
/uploads/*  https://xxxx-xxxx.trycloudflare.com/uploads/:splat  200
/*          /index.html                                     200
```

然后：
```bash
cd promoter-performance-tracker/frontend
npm install
npm run build
git add -A
git commit -m "switch tunnel"
git push
```

Netlify 自动部署 → 搞定！

---

## 从快速模式切回默认后端

把 `_redirects` 改回之前的地址，重新 build 推送。

---

> 💡 **提示：** 电脑关机后 Tunnel 自动断开。下次开机重新做"步骤 1-3"就行。想让 AI 助手自动帮你做，给它这段 prompt：
>
> ```
> 请帮我把 localhost:8000 用 cloudflared 暴露到公网，
> 然后更新 promoter-performance-tracker/frontend/public/_redirects 
> 指向新的 trycloudflare URL，重新 build 并 push 到 GitHub。
> ```
