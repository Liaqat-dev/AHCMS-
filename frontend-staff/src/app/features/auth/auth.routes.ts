import { Routes } from '@angular/router';

/**
 * Staff accounts are created by an administrator under `users:write` — there
 * is no public sign-up endpoint, so there is no registration page here.
 */
export const authRoutes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: 'login', loadComponent: () => import('./login/login').then((m) => m.Login) },
];
