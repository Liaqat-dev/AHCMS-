import { Injectable, computed, signal } from '@angular/core';

/** The staff principal, exactly as the auth endpoints return it. */
export interface StaffUser {
  id: string;
  email: string;
  full_name: string | null;
  roles: string[];
  permissions: string[];
}

/**
 * Holds the access token in memory only — never localStorage/sessionStorage,
 * where any XSS could read it. Durability comes from the httpOnly refresh
 * cookie instead: on boot, `AuthService.restore()` trades it for a new token.
 *
 * Roles and permissions here mirror the token's claims and are used purely to
 * shape the UI. They are not a security boundary — the API re-checks every
 * request, and permission changes only land on the next login or refresh.
 */
@Injectable({ providedIn: 'root' })
export class TokenService {
  private readonly _accessToken = signal<string | null>(null);
  private readonly _user = signal<StaffUser | null>(null);

  readonly accessToken = this._accessToken.asReadonly();
  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._user() !== null);

  set(token: string, user: StaffUser): void {
    this._accessToken.set(token);
    this._user.set(user);
  }

  clear(): void {
    this._accessToken.set(null);
    this._user.set(null);
  }

  has(permission: string): boolean {
    return this._user()?.permissions.includes(permission) ?? false;
  }

  hasRole(role: string): boolean {
    return this._user()?.roles.includes(role) ?? false;
  }
}
