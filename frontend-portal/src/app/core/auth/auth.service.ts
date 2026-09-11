import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable, catchError, finalize, map, of, shareReplay } from "rxjs";

import { environment } from "../../../environments/environment";
import { Student, TokenService } from "./token.service";

interface StudentTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  student: Student;
}

/**
 * Student authentication against `/api/v1/auth/student`.
 *
 * Students log in with a roll number, not an email, and hold a refresh cookie
 * that is named and path-scoped separately from the staff one — so signing in
 * here never disturbs a staff session in the same browser.
 */
@Injectable({ providedIn: "root" })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly tokens = inject(TokenService);
  private readonly base = `${environment.apiUrl}/auth/student`;

  /**
   * The in-flight refresh, shared between callers. Each refresh rotates the
   * cookie secret, so parallel refreshes would make the losers present an
   * already-rotated secret — which the backend reads as token theft and
   * answers by revoking the entire session.
   */
  private inFlightRefresh: Observable<string> | null = null;

  login(rollNo: string, password: string): Observable<Student> {
    return this.http
      .post<StudentTokenResponse>(`${this.base}/login`, {
        roll_no: rollNo,
        password,
      })
      .pipe(map((res) => this.accept(res)));
  }

  refresh(): Observable<string> {
    this.inFlightRefresh ??= this.http
      .post<StudentTokenResponse>(`${this.base}/refresh`, {})
      .pipe(
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

  /** Restore a session at startup; false simply means "not signed in". */
  restore(): Observable<boolean> {
    return this.refresh().pipe(
      map(() => true),
      catchError(() => of(false)),
    );
  }

  private accept(res: StudentTokenResponse): Student {
    this.tokens.set(res.access_token, res.student);
    return res.student;
  }
}
