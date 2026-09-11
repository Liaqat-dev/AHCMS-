import { Component, computed, inject } from "@angular/core";
import { Router, RouterOutlet } from "@angular/router";

import { AuthService } from "../../core/auth/auth.service";
import { TokenService } from "../../core/auth/token.service";

/**
 * Portal shell. There is no navigation: the portal is a single page, because
 * `GET /api/v1/student/me` is the entire surface a student token can open.
 */
@Component({
  selector: "app-portal-shell",
  imports: [RouterOutlet],
  template: `
    <div class="min-h-screen bg-slate-50 text-slate-900">
      <header class="border-b border-slate-200 bg-white">
        <div class="mx-auto flex max-w-3xl items-center gap-4 px-4 py-3">
          <span class="text-lg font-semibold text-emerald-600"
            >Student Portal</span
          >
          <span class="flex-1"></span>
          <span class="text-sm text-slate-500">{{ displayName() }}</span>
          <button
            type="button"
            (click)="signOut()"
            class="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-700 hover:bg-slate-50"
          >
            Sign out
          </button>
        </div>
      </header>
      <main class="mx-auto max-w-3xl px-4 py-8">
        <router-outlet />
      </main>
    </div>
  `,
})
export class PortalShell {
  private readonly tokens = inject(TokenService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly displayName = computed(
    () => this.tokens.student()?.full_name ?? "",
  );

  protected signOut(): void {
    this.auth.logout().subscribe(() => void this.router.navigate(["/login"]));
  }
}
