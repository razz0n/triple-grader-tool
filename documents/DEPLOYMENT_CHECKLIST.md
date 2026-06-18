# Deployment Security Checklist

## Pre-Deployment (Local)

- [ ] `.env` file is in `.gitignore` (never committed)
- [ ] `.env.example` created with template values (no secrets)
- [ ] `backend/requirements.txt` is up to date
- [ ] `frontend/package.json` is up to date
- [ ] All dependencies installed locally
- [ ] Application runs successfully locally with `STORAGE_BACKEND=database`
- [ ] Tests pass (if applicable)
- [ ] No hardcoded secrets in code
- [ ] CORS_ORIGINS list prepared for production URLs

## GitHub Repository

- [ ] Push all code to `main` branch
- [ ] Tags created for versioning (e.g., `v1.0.0`)
- [ ] No `.env` files in git history (check with `git log --all --full-history -- "**/.env"`)
- [ ] GitHub repository is private (if handling sensitive data)

## Supabase Setup

- [ ] Project created on Supabase
- [ ] Session Pooler enabled (port 5432)
- [ ] Connection string copied (Session, not Direct)
- [ ] Database tables initialized
- [ ] Row-Level Security (RLS) enabled on tables:
  - [ ] `users` table
  - [ ] `tokens` table
  - [ ] `sessions` table
- [ ] Automated backups enabled
- [ ] Connection limits reviewed (free tier: 2 concurrent)
- [ ] Created `.env.example` with pool URL format

## Render Setup

### Backend Service

- [ ] Render account created at render.com
- [ ] GitHub repository connected to Render
- [ ] Backend service created:
  - [ ] Runtime: Python 3.11
  - [ ] Build Command: `pip install -r backend/requirements.txt`
  - [ ] Start Command: `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port $PORT`
  - [ ] Plan: Starter (or Paid for production)

- [ ] Environment Variables set in Render dashboard:
  - [ ] `DATABASE_URL` = Supabase Session Pooler connection string
  - [ ] `STORAGE_BACKEND` = `database`
  - [ ] `CORS_ORIGINS` = your frontend URL + local dev URLs
  
- [ ] Health check configured: `/docs`
- [ ] Auto-deploy enabled for `main` branch
- [ ] Deploy button clicked → Deployment successful
- [ ] Check logs for errors: Render Dashboard → Logs

### Frontend Service

- [ ] Frontend service created:
  - [ ] Type: Static Site
  - [ ] Build Command: `cd frontend && npm install && npm run build`
  - [ ] Publish Directory: `frontend/dist`
  - [ ] Plan: Free/Starter
  
- [ ] Environment Variables set:
  - [ ] `VITE_API_URL` = Your Render backend URL (e.g., `https://ontology-grader-backend.onrender.com/api`)
  
- [ ] Deploy button clicked → Build successful
- [ ] Static files deployed

## Post-Deployment Testing

### Backend Health

- [ ] [ ] Test endpoint: `https://your-backend.onrender.com/docs` → Swagger UI loads
- [ ] [ ] Database initialization: Tables exist in Supabase
- [ ] [ ] Test API call: 
  ```bash
  curl https://your-backend.onrender.com/api/sessions \
    -H "Authorization: Bearer test-token"
  ```

### Frontend

- [ ] Frontend loads at `https://your-frontend.onrender.com`
- [ ] Check browser console for errors (F12 → Console)
- [ ] API calls successfully reach backend (check Network tab)
- [ ] CORS errors not present

### Database

- [ ] Supabase Dashboard → Logs shows no connection errors
- [ ] Tables contain data from test operations
- [ ] Backups are running

## Monitoring (Ongoing)

- [ ] Render logs checked daily for errors
- [ ] Supabase logs monitored for connection issues
- [ ] Uptime monitored (Render provides status page)
- [ ] Database performance checked (Supabase → SQL Editor → Analytics)
- [ ] Backup logs reviewed (Supabase → Backups)

## Secret Management

- [ ] Secrets stored in Render environment variables (not `.env` files)
- [ ] Secrets are encrypted at rest in Render
- [ ] No secrets visible in GitHub (checked with `git grep`)
- [ ] Database user password changed from default
- [ ] All service accounts follow principle of least privilege

## Production Hardening (Before Public Launch)

- [ ] HTTPS enforced (Render provides free SSL)
- [ ] Rate limiting configured (optional: use FastAPI middleware)
- [ ] CORS restricted to known domains only
- [ ] Input validation on all API endpoints
- [ ] SQL injection protection enabled (SQLAlchemy ORM)
- [ ] XSS protection headers added (Frontend)
- [ ] CSRF tokens implemented (if applicable)
- [ ] Error messages don't leak sensitive information
- [ ] Logging configured (don't log passwords or tokens)
- [ ] Database connection pool configured optimally

## Troubleshooting Notes

### If Backend Won't Deploy
1. Check `requirements.txt` exists in `backend/` directory
2. Review build logs in Render for dependency errors
3. Verify `backend/main.py` exists and has valid syntax
4. Ensure `render.yaml` has correct Python runtime

### If Database Connection Fails
1. Verify DATABASE_URL in Render matches Supabase Session Pooler (not Direct)
2. Check password contains special chars (encode as %XX if needed)
3. Test locally: `psycopg db_url`
4. Check Supabase firewall: Database → Networking → Allow all (for testing only)

### If CORS Errors Occur
1. Verify CORS_ORIGINS includes your frontend URL exactly
2. Check browser requests include `Origin` header
3. Restart backend service in Render after changing CORS_ORIGINS

## Rollback Procedure

If deployment causes issues:
1. Render Dashboard → Web Service → Deployments
2. Click previous deployment to rollback
3. Or revert git commit: `git revert <commit-hash>`
4. Push to main: automatically redeploys

---

**Last Updated:** 2026-06-02
**Version:** 1.0
**Status:** ✓ Ready for Production
