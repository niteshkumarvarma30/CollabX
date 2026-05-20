# Instagram Insights Dashboard (Multi-user SaaS)

A local full-stack Instagram analytics dashboard built with:

- React + Vite frontend
- FastAPI backend
- Meta/Facebook OAuth 2.0 authorization code flow
- Instagram Graph API
- Local SQLite persistence

Project location on this computer:

```txt
C:\Users\varni\Documents\Codex\2026-04-29\build-a-full-stack-application-called
```

## Product Goal

Users can open the web app, click **Connect Instagram**, authorize through Meta/Facebook OAuth, and view analytics for their connected Instagram Business or Creator account.

Users never enter:

- Instagram passwords
- Facebook passwords
- Meta app secrets
- Access tokens

All account access happens through OAuth.

## Architecture

```txt
React frontend
  -> FastAPI backend
  -> Meta OAuth / Facebook Login for Business
  -> Meta Graph API
  -> Instagram Graph API
  -> SQLite local database
```

## Folder Structure

```txt
backend/
  main.py
  requirements.txt
  .env
  instagram_dashboard.sqlite3

frontend/
  App.jsx
  index.html
  package.json
  src/
    main.jsx
    styles.css

run_all.bat
start_backend.bat
start_frontend.bat
README.md
```

## Meta Developer Setup

Create/configure one Meta app as the SaaS owner. Normal dashboard users should not create their own developer app.

Recommended app creation choices:

```txt
Use case: Other
App type: Business
```

Add these products:

- Facebook Login for Business
- Instagram

Configure OAuth redirect URI:

```txt
http://localhost:8000/callback
```

For production, use your real HTTPS URL, for example:

```txt
https://yourdomain.com/callback
```

Required permissions/scopes:

```txt
pages_show_list
pages_read_engagement
instagram_basic
instagram_manage_insights
```

Important Meta notes:

- In Development mode, only app Admins/Developers/Testers can authorize.
- For real customers, the app must be in Live mode and required permissions may need Meta App Review.
- Users still need a Facebook Page connected to an Instagram Business or Creator account.
- The app UI can request permissions, but it cannot add/approve permissions in Meta Developer Dashboard.

## Environment Configuration

Edit:

```txt
backend/.env
```

Example:

```env
META_APP_ID=your_meta_app_id
META_APP_SECRET=your_meta_app_secret
META_GRAPH_VERSION=v25.0
FRONTEND_URL=http://localhost:5173
META_PAGE_ID=your_page_id_optional_fallback
META_SCOPES=pages_show_list,pages_read_engagement,instagram_basic,instagram_manage_insights
```

`META_APP_SECRET` must stay only in the backend. Do not put it in frontend code.

`META_PAGE_ID` is optional. It is useful when Meta returns `0` pages from `/me/accounts`, but a specific Page ID is accessible through `/{PAGE_ID}`.

## Install Dependencies

Backend:

```powershell
cd C:\Users\varni\Documents\Codex\2026-04-29\build-a-full-stack-application-called\backend
python -m pip install -r requirements.txt
```

Frontend:

```powershell
cd C:\Users\varni\Documents\Codex\2026-04-29\build-a-full-stack-application-called\frontend
npm install
```

If PowerShell blocks `npm`, use:

```powershell
npm.cmd install
```

## Run Locally

Option 1: double-click:

```txt
run_all.bat
```

This opens two command windows:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

Option 2: run manually.

Backend:

```powershell
cd C:\Users\varni\Documents\Codex\2026-04-29\build-a-full-stack-application-called\backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd C:\Users\varni\Documents\Codex\2026-04-29\build-a-full-stack-application-called\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Open:

```txt
http://127.0.0.1:5173/
```

## OAuth Flow

1. User clicks **Connect Instagram**.
2. Frontend redirects to backend:

```txt
GET /login
```

3. Backend redirects to Meta OAuth:

```txt
https://www.facebook.com/v25.0/dialog/oauth
```

with scopes:

```txt
pages_show_list,pages_read_engagement,instagram_basic,instagram_manage_insights
```

4. Meta redirects back:

```txt
GET /callback?code=...
```

5. Backend exchanges the code for an access token.
6. Backend fetches Pages, Instagram account, media, and insights.
7. Frontend displays the dashboard.

## Data Pipeline

Backend requests:

```txt
GET /me/accounts
GET /{PAGE_ID}?fields=instagram_business_account
GET /{IG_USER_ID}?fields=id,username,followers_count
GET /{IG_USER_ID}/media?fields=id,caption
GET /{MEDIA_ID}/insights?metric=reach,likes,comments,saved,shares
```

If `/me/accounts` returns no pages, the app also tries:

```txt
GET /me?fields=accounts.limit(25){id,name,access_token,instagram_business_account}
```

If `META_PAGE_ID` is set, it can fallback to:

```txt
GET /{META_PAGE_ID}?fields=id,name,access_token,instagram_business_account
```

## Dashboard Calculations

Engagement rate:

```txt
(likes + comments + saved + shares) / reach
```

If reach is `0`, engagement rate is returned as `0`.

## Backend API Endpoints

```txt
GET /health
```

Health check.

```txt
GET /login
```

Starts Meta OAuth.

```txt
GET /login?fresh=true
```

Starts a stronger reconnect flow using Meta reauthorization.

```txt
GET /callback
```

OAuth callback from Meta.

```txt
GET /fetch-data
```

Returns Instagram dashboard data for the connected browser session.

```txt
GET /debug/meta
```

Shows required permission status and Page results from Meta. Does not expose tokens.

```txt
GET /debug/page/{page_id}
```

Tests whether the current OAuth token can access a specific Facebook Page ID.

## Frontend Features

- Connection wizard
- Connect Instagram button
- Reconnect with permissions button
- Loading spinner
- Friendly error messages
- Total posts
- Followers count
- Post table
- Sort by engagement
- Top-performing post highlight

## Local Storage

Connected sessions are stored in:

```txt
backend/instagram_dashboard.sqlite3
```

This lets a connected browser session survive backend restarts.

For production, replace this with a secure hosted database and encrypt tokens.

## Common Problems

### Invalid Scopes

Error:

```txt
Invalid Scopes: pages_show_list, pages_read_engagement, instagram_basic, instagram_manage_insights
```

Cause:

The Meta app does not support those permissions yet.

Fix:

- Use a Business-compatible Meta app.
- Add Facebook Login for Business.
- Add Instagram product.
- Add/request the required permissions.
- Add your user as Admin/Developer/Tester while in Development mode.

### No Facebook Pages Returned

Error:

```txt
Meta returned 0 Facebook Pages from /me/accounts
```

Possible causes:

- Facebook user does not have full Page access.
- App is in Development mode and user is not an app role member.
- Page is not selected during Meta OAuth.
- Instagram account is not connected to the Facebook Page.
- Page is available only through direct Page ID lookup.

Useful diagnostic:

```txt
http://localhost:8000/debug/page/YOUR_PAGE_ID
```

### Backend Restarted And Session Missing

If the browser cookie is missing or a different browser is used, connect again.

SQLite stores tokens locally, but the user still needs the same session cookie.

### Changed Meta App ID

If `META_APP_ID` changes, reconnect. Tokens from the old Meta app cannot be used with the new Meta app.

## Opening In Another IDE

Open this folder as the project root:

```txt
C:\Users\varni\Documents\Codex\2026-04-29\build-a-full-stack-application-called
```

Recommended terminal layout:

Terminal 1:

```powershell
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Then open:

```txt
http://127.0.0.1:5173/
```

## Security Notes

- Never expose `META_APP_SECRET` in frontend code.
- Never ask users to paste access tokens.
- Never ask users for Facebook/Instagram passwords.
- OAuth tokens should be encrypted in production.
- Use HTTPS in production.
- Replace local SQLite with a production database for real SaaS usage.

## Production Checklist

- Use a real domain.
- Set production redirect URI:

```txt
https://yourdomain.com/callback
```

- Configure Privacy Policy URL in Meta.
- Configure Terms URL if required.
- Submit required permissions for App Review.
- Switch Meta app to Live mode.
- Use HTTPS.
- Store tokens encrypted.
- Add user accounts/auth for your SaaS.
- Add token refresh/expiration handling.
- Add background sync and rate-limit handling.
