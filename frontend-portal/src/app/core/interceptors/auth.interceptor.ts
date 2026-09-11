import {
  HttpErrorResponse,
  HttpInterceptorFn,
  HttpRequest,
} from "@angular/common/http";
import { inject } from "@angular/core";
import { Router } from "@angular/router";
import { catchError, switchMap, throwError } from "rxjs";

import { AuthService } from "../auth/auth.service";
import { TokenService } from "../auth/token.service";

/**
 * The auth flow itself. A 401 from any of these is a real answer ("bad roll
 * number or password", "no session"), not a stale access token, so refreshing
 * and retrying would loop.
 */
const AUTH_ENDPOINTS = [
  "/auth/student/login",
  "/auth/student/refresh",
  "/auth/student/logout",
];

const isAuthEndpoint = (url: string): boolean =>
  AUTH_ENDPOINTS.some((endpoint) => url.includes(endpoint));

/**
 * Attaches the bearer token, sends the refresh cookie, and transparently
 * renews a 15-minute access token that expired mid-session: on a 401 it
 * refreshes once (shared across concurrent failures by `AuthService`) and
 * replays the original request.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const tokens = inject(TokenService);
  const auth = inject(AuthService);
  const router = inject(Router);

  const authorize = (request: HttpRequest<unknown>): HttpRequest<unknown> => {
    // withCredentials on every call: the API is same-origin, and the refresh
    // cookie is scoped by path so only the auth endpoints actually receive it.
    const authorized = request.clone({ withCredentials: true });
    const token = tokens.accessToken();
    return token
      ? authorized.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : authorized;
  };

  return next(authorize(req)).pipe(
    catchError((error: unknown) => {
      const expired =
        error instanceof HttpErrorResponse && error.status === 401;
      if (!expired || isAuthEndpoint(req.url)) {
        return throwError(() => error);
      }
      return auth.refresh().pipe(
        switchMap(() => next(authorize(req))),
        catchError(() => {
          // The refresh cookie is gone, expired, or revoked: session over.
          tokens.clear();
          void router.navigate(["/login"]);
          return throwError(() => error);
        }),
      );
    }),
  );
};
