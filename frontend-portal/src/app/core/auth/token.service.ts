import { Injectable, computed, signal } from "@angular/core";

/**
 * The student principal, exactly as the portal endpoints return it.
 *
 * Note what is absent: no roles, no permissions. A student is not a staff
 * `User` — the backend gives them a token whose `sub_type` is `"student"`, and
 * every staff endpoint refuses it with 403. There is nothing to gate on here.
 */
export interface Student {
  id: string;
  roll_no: string;
  full_name: string;
  email: string | null;
}

/**
 * Holds the access token in memory only — never localStorage/sessionStorage.
 * Durability comes from the httpOnly refresh cookie: on boot,
 * `AuthService.restore()` trades it for a fresh access token.
 */
@Injectable({ providedIn: "root" })
export class TokenService {
  private readonly _accessToken = signal<string | null>(null);
  private readonly _student = signal<Student | null>(null);

  readonly accessToken = this._accessToken.asReadonly();
  readonly student = this._student.asReadonly();
  readonly isAuthenticated = computed(() => this._student() !== null);

  set(token: string, student: Student): void {
    this._accessToken.set(token);
    this._student.set(student);
  }

  clear(): void {
    this._accessToken.set(null);
    this._student.set(null);
  }
}
