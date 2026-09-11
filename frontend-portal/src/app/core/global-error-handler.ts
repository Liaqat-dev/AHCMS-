import { ErrorHandler, Injectable } from "@angular/core";

/**
 * App-wide error handler.
 * TODO: forward to a monitoring service (Sentry, etc.) instead of the console.
 */
@Injectable()
export class GlobalErrorHandler implements ErrorHandler {
  handleError(error: unknown): void {
    console.error("[GlobalErrorHandler]", error);
  }
}
