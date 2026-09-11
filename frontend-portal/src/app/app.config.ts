import {
  ApplicationConfig,
  ErrorHandler,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
  provideZonelessChangeDetection,
} from "@angular/core";
import {
  provideHttpClient,
  withFetch,
  withInterceptors,
} from "@angular/common/http";
import { provideRouter, withComponentInputBinding } from "@angular/router";
import { firstValueFrom } from "rxjs";

import { routes } from "./app.routes";
import { AuthService } from "./core/auth/auth.service";
import { authInterceptor } from "./core/interceptors/auth.interceptor";
import { errorInterceptor } from "./core/interceptors/error.interceptor";
import { GlobalErrorHandler } from "./core/global-error-handler";

export const appConfig: ApplicationConfig = {
  providers: [
    provideZonelessChangeDetection(),
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(
      withFetch(),
      withInterceptors([authInterceptor, errorInterceptor]),
    ),
    // Registered as a class *and* aliased onto the ErrorHandler token: the
    // error interceptor injects GlobalErrorHandler directly, which useClass
    // alone does not bind (it only provides the ErrorHandler token, so the
    // interceptor threw NG0201 and every request died before it was sent).
    // useExisting rather than a second useClass, so both resolve to one instance.
    GlobalErrorHandler,
    { provide: ErrorHandler, useExisting: GlobalErrorHandler },
    // Trade the httpOnly refresh cookie for an access token before the router
    // runs, so a reload keeps the student signed in. Resolves to false when
    // there is no session — not an error.
    provideAppInitializer(() => firstValueFrom(inject(AuthService).restore())),
  ],
};
