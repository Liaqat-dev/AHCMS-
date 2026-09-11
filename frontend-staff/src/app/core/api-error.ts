import { HttpErrorResponse } from '@angular/common/http';

import { ApiError } from './models/api';

/** Pull the message out of the backend's `{ error: { code, message } }` envelope. */
export function apiErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (!(error instanceof HttpErrorResponse)) {
    return fallback;
  }
  if (error.status === 0) {
    return 'Cannot reach the server. Is the API running?';
  }
  const body = error.error as Partial<ApiError> | null;
  return body?.error?.message ?? fallback;
}
