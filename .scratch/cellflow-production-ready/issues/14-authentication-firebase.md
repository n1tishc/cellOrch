# 14 — Authentication (Firebase)

**What to build:** Every endpoint is wide open — `POST /seed` can spawn infinite runs, `POST /runs/{id}/inject-fault` can sabotage any run, and CORS is `allow_origins=["*"]`. This ticket adds Google sign-in to the dashboard and Firebase ID token verification to the backend, gating mutation endpoints behind authentication.

**Blocked by:**
- [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)
- [05 — Real-Time Dashboard (SSE)](./05-real-time-dashboard-sse.md)

**Status:** ready-for-agent

- [ ] Add `firebase-admin` to orchestrator requirements
- [ ] Initialize Firebase Admin SDK in the orchestrator (service account from env or application default credentials)
- [ ] Add a `get_current_user` FastAPI dependency that extracts and verifies the Firebase ID token from the `Authorization: Bearer <token>` header
- [ ] Apply the auth dependency to all mutation endpoints: `POST /runs`, `POST /seed`, `POST /runs/{id}/inject-fault`, `POST /runs/{id}/pause`, `POST /runs/{id}/resume`, `POST /runs/{id}/cancel`
- [ ] Keep read endpoints (`GET /runs`, `GET /runs/{id}`, `GET /metrics`, `GET /resources`, `GET /runs/stream`) accessible without auth (or make this configurable)
- [ ] Add Firebase client SDK to the frontend (`npm install firebase`)
- [ ] Add a "Sign in with Google" button to the dashboard header
- [ ] After sign-in, attach the Firebase ID token to all API requests (fetch interceptor or wrapper)
- [ ] Add a sign-out button and handle token expiry (refresh or re-prompt)
- [ ] Restrict CORS to the frontend's origin instead of `["*"]`
- [ ] Verify: unauthenticated mutation requests return 401
- [ ] Verify: authenticated requests succeed and the user identity is available in the request context
- [ ] Verify: the SSE stream works for authenticated users
