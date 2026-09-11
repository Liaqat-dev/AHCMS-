import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, finalize, map, of, shareReplay } from 'rxjs';

import { environment } from '../../../environments/environment';
import { StaffUser, TokenService } from './token.service';

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: StaffUser;
}

/**
 * Staff authentication against `/api/v1/auth`.
 *
 * Every call is same-origin, so the httpOnly refresh cookie travels as a
 * first-party cookie and is never exposed to JS.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly tokens = inject(TokenService);
  private readonly base = `${environment.apiUrl}/auth`;

  /**
   * The in-flight refresh, shared between callers. Without this, a page that
   * fires several requests at once would kick off one refresh each — and since
   * every refresh rotates the cookie secret, the losers would present an
   * already-rotated secret and trip the backend's reuse detection, revoking
   * the whole session.
   */
  private inFlightRefresh: Observable<string> | null = null;

  login(email: string, password: string): Observable<StaffUser> {
    return this.http
      .post<TokenResponse>(`${this.base}/login`, { email, password })
      .pipe(map((res) => this.accept(res)));
  }

  refresh(): Observable<string> {
    this.inFlightRefresh ??= this.http.post<TokenResponse>(`${this.base}/refresh`, {}).pipe(
      map((res) => {
        this.accept(res);
        return res.access_token;
      }),
      finalize(() => (this.inFlightRefresh = null)),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.inFlightRefresh;
  }

  logout(): Observable<void> {
    return this.http.post<void>(`${this.base}/logout`, {}).pipe(
      // An already-dead session is still a successful logout locally.
      catchError(() => of(undefined)),
      map(() => {
        this.tokens.clear();
      }),
    );
  }

  /**
   * Restore a session at startup. The access token is memory-only, so after a
   * reload the refresh cookie is the only evidence of a session. A failure is
   * the ordinary "not signed in" path, not an error worth surfacing.
   */
  restore(): Observable<boolean> {
    return this.refresh().pipe(
      map(() => true),
      catchError(() => of(false)),
    );
  }

  private accept(res: TokenResponse): StaffUser {
    this.tokens.set(res.access_token, res.user);
    return res.user;
  }
}
