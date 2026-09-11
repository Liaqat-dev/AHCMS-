import { inject } from '@angular/core';
import {
  ActivatedRouteSnapshot,
  CanActivateChildFn,
  CanActivateFn,
  Router,
  UrlTree,
} from '@angular/router';

import { NavRouteData } from '../../layout/nav';
import { TokenService } from './token.service';

/**
 * Gate for every staff route. The silent refresh in `app.config.ts` runs to
 * completion before the router bootstraps, so a signed-in user surviving a
 * page reload is already restored by the time this runs.
 */
export const staffGuard: CanActivateFn = (_route, state): boolean | UrlTree => {
  const router = inject(Router);
  if (inject(TokenService).isAuthenticated()) {
    return true;
  }
  return router.createUrlTree(['/auth/login'], {
    queryParams: state.url === '/' ? {} : { redirectTo: state.url },
  });
};

/**
 * Gate a route on a permission code. Cosmetic only — it keeps users out of
 * pages that would just 403, and the API enforces the same rule for real.
 */
export const requirePermission =
  (code: string): CanActivateFn =>
  (): boolean | UrlTree => {
    const tokens = inject(TokenService);
    const router = inject(Router);
    if (!tokens.isAuthenticated()) {
      return router.createUrlTree(['/auth/login']);
    }
    return tokens.has(code) || router.createUrlTree(['/dashboard']);
  };

/**
 * Gate every shell child on the permission declared in its own `data.nav`.
 *
 * The sidebar reads the same field to decide what to show, so a section's
 * permission is written once on the route instead of twice — once in a
 * `canActivate` and once in a nav list that can drift from it.
 */
export const navGuard: CanActivateChildFn = (route: ActivatedRouteSnapshot) => {
  const code = (route.data as NavRouteData | undefined)?.nav?.permission;
  return code ? requirePermission(code)(route, route as never) : true;
};
