import { inject } from "@angular/core";
import { CanActivateFn, Router, UrlTree } from "@angular/router";

import { TokenService } from "./token.service";

/**
 * Gate for the portal. The silent refresh in `app.config.ts` completes before
 * the router bootstraps, so a signed-in student surviving a reload is already
 * restored by the time this runs.
 */
export const studentGuard: CanActivateFn = (
  _route,
  state,
): boolean | UrlTree => {
  const router = inject(Router);
  if (inject(TokenService).isAuthenticated()) {
    return true;
  }
  return router.createUrlTree(["/login"], {
    queryParams: state.url === "/" ? {} : { redirectTo: state.url },
  });
};
