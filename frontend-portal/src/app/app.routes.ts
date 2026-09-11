import { Routes } from "@angular/router";

import { studentGuard } from "./core/auth/student.guard";

/**
 * Student portal routes. The whole application is one student looking at their
 * own record — staff management lives in the separate `frontend-staff/` app,
 * and a student token is refused by every endpoint behind it.
 */
export const routes: Routes = [
  {
    path: "",
    loadComponent: () =>
      import("./layout/portal-shell/portal-shell").then((m) => m.PortalShell),
    canActivate: [studentGuard],
    children: [
      { path: "", pathMatch: "full", redirectTo: "profile" },
      {
        path: "profile",
        loadComponent: () =>
          import("./features/profile/profile").then((m) => m.Profile),
      },
    ],
  },
  {
    path: "login",
    loadComponent: () => import("./features/login/login").then((m) => m.Login),
  },
  { path: "**", redirectTo: "" },
];
