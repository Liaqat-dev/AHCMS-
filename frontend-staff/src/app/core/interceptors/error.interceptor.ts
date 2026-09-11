import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { GlobalErrorHandler } from '../global-error-handler';

/**
 * Logs server faults centrally and rethrows. Runs after `authInterceptor`, so
 * a 401 that was recovered by a token refresh never reaches here.
 *
 * TODO: surface 5xx to the user via a toast service once one exists.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const handler = inject(GlobalErrorHandler);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && (error.status >= 500 || error.status === 0)) {
        handler.handleError(error);
      }
      return throwError(() => error);
    }),
  );
};
