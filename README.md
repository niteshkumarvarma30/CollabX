# Instagram Insights Dashboard (CollabX)

A full-stack Instagram analytics dashboard (SaaS) built to let users connect their Instagram Professional/Business accounts via Meta OAuth and view detailed engagement insights.

---

## 🚀 What We Have Done (Recent Upgrades & Fixes)

We successfully took the application from a local-only prototype and fully deployed it to production with robust, stateful multi-user architecture:

1. **Production Deployment on Render**:
   - **Frontend**: Deployed as a static site on Render (`collabx-web`).
   - **Backend**: Deployed as a Python FastAPI service on Render (`collabx-api`).

2. **Persistent Database Migration (Supabase)**:
   - Render's free tier spins down servers after inactivity, which previously cleared all in-memory OAuth states and local SQLite database files.
   - **Solution**: Migrated all sessions and OAuth state tracking to a hosted **PostgreSQL database on Supabase**. Your data and sessions now survive server restarts.

3. **Secure Auth Architecture (Bypassing Cookie Blocks)**:
   - Modern browsers block cross-site cookies (Third-Party Cookies) between different domains (e.g., frontend on `render.com` communicating with backend on `onrender.com`).
   - **Solution**: Re-engineered authentication to use a **URL-based redirection token pass** combined with secure **`localStorage`** on the client side.

4. **Business Suite / Portfolio Integration**:
   - If a page is connected to a Meta Business Portfolio (Business Suite), Meta filters it out from the standard `/me/accounts` endpoint.
   - **Solution**: Added the **`business_management`** scope to the OAuth flow and configuration, enabling the dashboard to fetch business-owned pages successfully.

5. **Meta Privacy Policy Compliance**:
   - Created and published a static compliance page (`privacy.html`) to satisfy Meta's strict production security checks.

---

## ⚙️ Architecture & Data Pipeline

```text
[React Frontend] (collabx-web.onrender.com)
       │
       ▼ (Fetch analytics / Trigger OAuth)
[FastAPI Backend] (collabx-api-1d0a.onrender.com)
       │
       ├─► [Supabase PostgreSQL DB] (oauth_states, user_sessions)
       │
       └─► [Meta / Instagram Graph API] (v25.0)
```

### Data Fetching Steps:
1. **User Login**: `/login` generates a secure unique state stored in Supabase, then redirects the user to Meta's OAuth dialog.
2. **Callback**: `/callback` receives the authorization code, exchanges it for a **User Access Token**, and fetches user info.
3. **Page Discovery**: Requests `/me/accounts` to retrieve managed Facebook Pages.
4. **Instagram Account Lookup**: Requests `/{PAGE_ID}?fields=instagram_business_account` to find the linked Instagram Business/Creator account.
5. **Media & Insights**: Fetches the last 25 posts and polls `/{MEDIA_ID}/insights` for engagement metrics (likes, comments, reach, saves, shares).
6. **Dashboard Stats**: Engagement Rate is calculated as:
   $$\text{Engagement Rate} = \frac{\text{Likes} + \text{Comments} + \text{Saves} + \text{Shares}}{\text{Reach}}$$

---

## 🛡️ Going Public: Removing the Developer Account Requirement

Currently, the app is in **Development Mode** (or Live Mode without approved permissions). Under this state, **only users added as Admins, Developers, or Testers who have registered Meta Developer accounts can log in.**

To make the app publicly available so **anyone** can log in with a normal Facebook account without creating a developer account, you must complete the **Meta App Review** process.

### Step-by-Step App Review & Upgrade Guide

#### Step 1: Ensure Prerequisites are Completed
- [x] **Privacy Policy URL** is set in Meta Settings (Basic) pointing to `https://<your-frontend>.onrender.com/privacy.html`.
- [x] **Category** is set to **Business and Pages** in Meta Settings.
- [x] **App Icon** (1024x1024) is uploaded.

#### Step 2: Request Permissions in App Review
Go to your **Meta Developer Dashboard** → **App Review** → **Permissions and Features**, and request **Advanced Access** for the following 5 permissions:
1. `pages_show_list` (To list the user's Facebook Pages)
2. `pages_read_engagement` (To read Page-level metrics)
3. `instagram_basic` (To read Instagram profile info)
4. `instagram_manage_insights` (To read post-level reach, impressions, engagement)
5. `business_management` (To read Pages connected to Meta Business portfolios)

#### Step 3: Record a Screencast Video
Meta requires a short video (under 2-3 minutes) demonstrating how the app uses these permissions. 
* **What to show in the video**:
  1. Show your website landing page.
  2. Click **Connect Instagram** and show the Facebook Login screen.
  3. Log in, select a page, select an Instagram account, and grant the permissions.
  4. Show the dashboard loading and displaying the follower count, posts table, and engagement rates.
  5. *Explain in the video description*: "We use `pages_show_list` and `business_management` to find the user's linked Facebook Page, which connects us to their Instagram Business ID via `instagram_basic`. We then fetch engagement data using `instagram_manage_insights` to present an aggregated analytics dashboard."

#### Step 4: Submit for Verification
* If you are running a registered business, you will need to complete **Business Verification**.
* If you are an individual developer, you can verify using your **personal ID** (Meta Individual Verification).
* Submit the review request. Meta typically takes **2 to 5 business days** to approve.

Once approved, toggle the app to **Live Mode** if it isn't already. **Anyone in the world can now log in instantly!**

---

## 💻 Running the App Locally

### 1. Configure Local Environment
Create/edit `backend/.env`:
```env
META_APP_ID=1519997772927886
META_APP_SECRET=da1ead8646789489f8db0c489700cf95
META_GRAPH_VERSION=v25.0
FRONTEND_URL=http://localhost:5173
DATABASE_URL=postgresql://postgres:<password>@db.mpxgkhwlgmiclmpylupp.supabase.co:5432/postgres
META_SCOPES=pages_show_list,pages_read_engagement,instagram_basic,instagram_manage_insights,business_management
```

### 2. Run the Servers
Double click **`run_all.bat`** in the root directory. This will start:
* **Backend**: `http://127.0.0.1:8000`
* **Frontend**: `http://127.0.0.1:5173`
