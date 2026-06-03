# Render Deployment Guide

## Overview
This guide covers safe deployment of the Ontology Grading Tool to Render.com with Supabase as the database backend.

## Architecture
```
GitHub Repository
    ↓
Render (CI/CD Pipeline)
├── Backend Service (FastAPI on :8000)
├── Frontend Build (React/Vite static)
└── → Supabase PostgreSQL (Cloud Database)
```

---

## Step 1: Prepare Your Repository

### 1a. Update .gitignore (✓ Already Done)
Ensure `.env` files are never committed:
```
.env
.env.local
backend/.env
frontend/.env
```

### 1b. Create Environment Templates
Create template files for reference (these show what variables are needed, without secrets):

**`backend/.env.example`:**
```
DATABASE_URL=postgresql://postgres:PASSWORD@pooler.supabase.com:5432/postgres
STORAGE_BACKEND=database
```

**`frontend/.env.example`:**
```
VITE_API_URL=https://your-app.onrender.com/api
```

---

## Step 2: Create Render Configuration

### 2a. Create `render.yaml` in repo root

This file tells Render how to build and deploy your app.

---

## Step 3: Supabase Security Setup

### 3a. Generate Row-Level Security (RLS) Policies
In Supabase Dashboard:
1. Go to **Authentication** → **Policies**
2. Enable RLS on all tables:
   - `users` table
   - `tokens` table
   - `sessions` table

### 3b. Create Database User (Optional but Recommended)
Instead of using `postgres` superuser:
1. In Supabase SQL Editor, run:
```sql
-- Create app-specific user
CREATE USER app_user WITH PASSWORD 'strong-random-password';
GRANT CONNECT ON DATABASE postgres TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
```

2. Update `.env` with this user:
```
DATABASE_URL=postgresql://app_user:strong-password@pooler.supabase.com:5432/postgres
```

### 3c. Enable Database Backups
Supabase: **Database** → **Backups** → Enable automated daily backups

---

## Step 4: Create Render Services

### 4a. Connect GitHub to Render
1. Go to [render.com](https://render.com)
2. Sign up/Login
3. Click **New +** → **Web Service**
4. Select **Connect a repository** → Choose your GitHub repo
5. Click **Connect**

### 4b. Deploy Backend Service

**Service Configuration:**
- **Name:** ontology-grader-backend
- **Environment:** Python 3.11
- **Build Command:** `pip install -r backend/requirements.txt`
- **Start Command:** `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000`
- **Region:** Choose closest to your users
- **Plan:** Free/Starter (auto-sleeps after 15 min inactivity) or Paid for production

**Environment Variables** (Set in Render dashboard):
```
DATABASE_URL=postgresql://postgres.XXXX:%23Password@aws-1-us-east-1.pooler.supabase.com:5432/postgres
STORAGE_BACKEND=database
```

✅ **Deploy**

### 4c. Deploy Frontend Service (Optional - CDN recommended)

**Option A: Static Site (Recommended)**
1. **Service Type:** Static Site
2. **Name:** ontology-grader-frontend
3. **Build Command:** `cd frontend && npm install && npm run build`
4. **Publish Directory:** `frontend/dist`

**Environment Variables:**
```
VITE_API_URL=https://ontology-grader-backend.onrender.com/api
```

**Option B: Service (less recommended for frontend)**
If you prefer to run frontend as a service instead of static.

---

## Step 5: Configure CORS & Security

### 5a. Update Backend CORS in `backend/main.py`

Replace this section:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # ... local dev URLs
    ],
```

With production URLs:
```python
import os

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

In Render, set environment variable:
```
CORS_ORIGINS=https://ontology-grader-frontend.onrender.com,https://yourdomain.com
```

### 5b. Update Frontend API URL in `frontend/src/api.js`

```javascript
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
```

This reads from `.env.local` in development or `VITE_API_URL` in Render.

---

## Step 6: Set Secrets Safely

**NEVER hardcode or commit:**
- Database passwords
- API keys
- Session secrets
- Auth tokens

**Use Render's Secrets Management:**
1. In Render Dashboard → Web Service → Environment
2. Click **Add Secret File** or **Add Environment Variable**
3. Name: `DATABASE_URL`
4. Value: Your Supabase connection string
5. Click **Save**

Render encrypts these and injects at runtime.

---

## Step 7: Deploy & Test

### 7a. Initial Deployment
- Render automatically deploys on every push to `main`
- Watch logs in Render dashboard
- Check for build/runtime errors

### 7b. Test Backend Health
```bash
curl https://your-app.onrender.com/docs
# Should see Swagger UI (FastAPI docs)
```

### 7c. Test Database Connection
```bash
curl https://your-app.onrender.com/api/sessions \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 7d. Database Initialization
First time only, initialize tables in Supabase:
```bash
# From your local machine:
DATABASE_URL="your-connection-string" python -c \
  "import sys; sys.path.insert(0, 'backend'); from database import Base, engine; Base.metadata.create_all(bind=engine)"
```

Or use Render's one-off job:
1. Render Dashboard → Web Service → Console
2. Run: `cd backend && python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"`

---

## Step 8: Monitoring & Maintenance

### 8a. Enable Application Logging
Render logs to stdout automatically. View in Dashboard.

### 8b. Set Up Error Tracking (Optional)
Add to `backend/requirements.txt`:
```
sentry-sdk
```

In `backend/main.py`:
```python
import sentry_sdk
sentry_sdk.init("YOUR_SENTRY_DSN")
```

### 8c. Monitor Supabase
- **Logs:** Supabase Dashboard → Logs
- **Backups:** Supabase Dashboard → Backups
- **Performance:** Supabase Dashboard → SQL Editor → Query analytics

---

## Troubleshooting

### Database Connection Failed
- Verify Supabase connection string in Render environment variables
- Check Supabase firewall (Supabase Dashboard → Database → Networking)
- Ensure pooler.supabase.com is not blocked

### CORS Errors in Frontend
- Check CORS_ORIGINS environment variable in Render
- Verify frontend URL matches exactly (including protocol)
- Clear browser cache

### Render Service Won't Start
- Check logs: Render Dashboard → Logs
- Verify `requirements.txt` is in root or `backend/`
- Ensure `backend/main.py` exists and is executable

### Static Files Not Loading
- Verify build directory in Render is correct (`frontend/dist`)
- Check `npm run build` completes successfully locally
- Ensure `index.html` is in `frontend/dist`

---

## Security Checklist

- [ ] `.env` files in `.gitignore`
- [ ] Credentials stored in Render secrets, not code
- [ ] Supabase RLS policies enabled on all tables
- [ ] CORS restricted to known domains
- [ ] Database user has least privilege (not superuser)
- [ ] HTTPS enforced (Render provides free SSL)
- [ ] Backups enabled on Supabase
- [ ] Logs monitored for errors
- [ ] Rate limiting configured (optional)
- [ ] Password hashing enabled in app

---

## Advanced: Custom Domain

1. Buy domain (GoDaddy, Namecheap, etc.)
2. Render Dashboard → Settings → Custom Domains
3. Add your domain
4. Update DNS records (Render provides instructions)
5. Update CORS_ORIGINS to include your domain

---

## Cost Estimate (Free Tier)

| Service | Cost | Limit |
|---------|------|-------|
| Render Backend | Free | Auto-sleeps after 15 min inactivity |
| Render Frontend | Free | Included in starter plan |
| Supabase | Free | 500MB DB, 2GB bandwidth/month |
| **Total** | **$0** | Suitable for small teams |

For production (paid):
- Render Backend: $7-50/month (depending on traffic)
- Render Frontend: Included
- Supabase: $25+/month (pro plan)

---

## Next Steps

1. Create `render.yaml` (see next file)
2. Commit changes: `git add .gitignore .env.example backend/.env.example`
3. Push to GitHub
4. Deploy on Render
5. Test endpoint health
6. Monitor logs for errors

Questions? Check:
- [Render Docs](https://render.com/docs)
- [Supabase Docs](https://supabase.com/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
