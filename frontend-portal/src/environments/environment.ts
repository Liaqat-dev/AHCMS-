// Dev environment. The SPA always calls the API same-origin at `/api/v1`:
// - locally, `proxy.conf.json` forwards /api → the backend;
// - on Vercel, a rewrite forwards /api → the Render backend.
export const environment = {
  production: false,
  apiUrl: "/api/v1",
};
