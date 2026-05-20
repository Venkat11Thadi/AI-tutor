# Deploying Zephyr Assist — Vercel (Frontend) + Render (Backend)

This guide walks you through deploying the full Zephyr Assist application using **Vercel** for the React frontend and **Render** for the FastAPI backend.

---

## Architecture Overview

```
┌─────────────────────┐       HTTPS        ┌─────────────────────┐
│   Vercel (Frontend)  │  ───────────────►  │   Render (Backend)   │
│   React + Vite       │  API requests      │   FastAPI + SQLite   │
│   Static hosting     │  ◄───────────────  │   Web service        │
└─────────────────────┘    JSON responses   └─────────────────────┘
```

---

## Part 1: Deploy the Backend on Render

### Step 1 — Push your code to GitHub

Make sure your entire project is pushed to a GitHub repository:

```bash
git add -A
git commit -m "prepare for deployment"
git push origin main
```

### Step 2 — Create a Render account

Go to [render.com](https://render.com) and sign up (free tier works).

### Step 3 — Create a new Web Service

1. Click **New** → **Web Service**
2. Connect your GitHub repository
3. Configure the service:

| Setting | Value |
| --- | --- |
| **Name** | `zephyr-assist-api` |
| **Region** | Choose closest to your users |
| **Branch** | `main` |
| **Root Directory** | *(leave empty — project root)* |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` (or `Starter` for persistent disk) |

### Step 4 — Set environment variables

In the Render dashboard, go to your service → **Environment** → **Add Environment Variable**:

| Key | Value | Notes |
| --- | --- | --- |
| `JWT_SECRET` | *(generate a random string, e.g. `openssl rand -hex 32`)* | **Required** — secures user tokens |
| `FRONTEND_URL` | `https://your-app.vercel.app` | **Required** — set this after deploying frontend |
| `PYTHON_VERSION` | `3.11.0` | Ensures correct Python version |
| `GROQ_API_KEY` | *(optional)* | Only if you want a server-side default key |

> **Note on SQLite**: Render's free tier has an ephemeral filesystem — the database resets on every deploy. For persistence, either upgrade to a paid instance with a **Persistent Disk**, or migrate to PostgreSQL using Render's managed database.

### Step 5 — Deploy

Click **Create Web Service**. Render will build and deploy automatically. Once done, you'll get a URL like:

```
https://zephyr-assist-api.onrender.com
```

Verify it works by visiting `https://zephyr-assist-api.onrender.com/health` — you should see `{"status": "ok"}`.

---

## Part 2: Deploy the Frontend on Vercel

### Step 1 — Create a Vercel account

Go to [vercel.com](https://vercel.com) and sign up with your GitHub account.

### Step 2 — Import the project

1. Click **Add New** → **Project**
2. Select your GitHub repository
3. Configure the project:

| Setting | Value |
| --- | --- |
| **Framework Preset** | `Vite` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |

### Step 3 — Set environment variables

In the Vercel project settings → **Environment Variables**, add:

| Key | Value |
| --- | --- |
| `VITE_TUTOR_API_URL` | `https://zephyr-assist-api.onrender.com` |

> **Important**: The variable **must** start with `VITE_` for Vite to expose it to the frontend at build time.

### Step 4 — Deploy

Click **Deploy**. Vercel will build and deploy automatically. You'll get a URL like:

```
https://zephyr-assist.vercel.app
```

### Step 5 — Update Render's CORS

Now go back to your **Render** dashboard and update the `FRONTEND_URL` environment variable:

```
FRONTEND_URL=https://zephyr-assist.vercel.app
```

Render will auto-redeploy with the updated CORS configuration.

---

## Post-Deployment Checklist

- [ ] Visit `https://your-backend.onrender.com/health` → should return `{"status": "ok"}`
- [ ] Visit `https://your-app.vercel.app` → should show the login page
- [ ] Register a new account
- [ ] Enter your Groq API key in Settings
- [ ] Send a message and verify the tutor responds

---

## Troubleshooting

### "Failed to fetch" errors in the browser
- Check the browser console for CORS errors
- Verify `FRONTEND_URL` on Render matches your exact Vercel URL (including `https://`)
- Verify `VITE_TUTOR_API_URL` on Vercel points to your exact Render URL

### Backend returns 500 on first request
- Render free-tier instances spin down after inactivity. The first request may take 30–60 seconds while the instance cold-starts.

### Database resets after every deploy
- Render's free tier uses an ephemeral filesystem. Upgrade to a paid plan with a **Persistent Disk** mounted at `/data`, then set:
  ```
  SQLITE_DB_PATH=/data/zephyr.sqlite3
  ```

### Vercel build fails
- Make sure the **Root Directory** is set to `frontend`
- Ensure `VITE_TUTOR_API_URL` doesn't have a trailing slash

---

## Custom Domain (Optional)

### Vercel
1. Go to **Settings** → **Domains** → Add your domain
2. Update DNS records as instructed by Vercel
3. Update `FRONTEND_URL` on Render to match the new domain

### Render
1. Go to **Settings** → **Custom Domains** → Add your domain
2. Update DNS records as instructed by Render
3. Update `VITE_TUTOR_API_URL` on Vercel to match the new domain and redeploy
