import { Component, inject, input, signal } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Router } from "@angular/router";

import { apiErrorMessage } from "../../core/api-error";
import { AuthService } from "../../core/auth/auth.service";

@Component({
  selector: "app-login",
  imports: [ReactiveFormsModule],
  template: `
    <div class="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div
        class="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h1 class="text-xl font-semibold text-slate-900">Student portal</h1>
        <p class="mt-1 text-sm text-slate-600">
          Sign in with your roll number.
        </p>

        <form class="mt-6 space-y-4" [formGroup]="form" (ngSubmit)="submit()">
          <div>
            <label class="block text-sm font-medium text-slate-700" for="rollNo"
              >Roll number</label
            >
            <input
              id="rollNo"
              type="text"
              formControlName="rollNo"
              autocomplete="username"
              placeholder="BSCS-2024-001"
              class="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm
                     focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <label
              class="block text-sm font-medium text-slate-700"
              for="password"
              >Password</label
            >
            <input
              id="password"
              type="password"
              formControlName="password"
              autocomplete="current-password"
              class="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm
                     focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          @if (error()) {
            <p
              class="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
              role="alert"
            >
              {{ error() }}
            </p>
          }

          <button
            type="submit"
            [disabled]="form.invalid || pending()"
            class="w-full rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white
                   hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {{ pending() ? "Signing in…" : "Sign in" }}
          </button>
        </form>

        <p class="mt-6 border-t border-slate-100 pt-4 text-xs text-slate-500">
          No password yet? Ask the college office to issue one for your roll
          number.
        </p>
      </div>
    </div>
  `,
})
export class Login {
  /** Bound from the `redirectTo` query param by `withComponentInputBinding()`. */
  readonly redirectTo = input("/profile");

  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly pending = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    rollNo: ["", [Validators.required]],
    // Matches the backend's own minimum, so a too-short password fails here
    // rather than costing a round trip.
    password: ["", [Validators.required, Validators.minLength(8)]],
  });

  protected submit(): void {
    if (this.form.invalid || this.pending()) {
      return;
    }
    this.pending.set(true);
    this.error.set(null);

    const { rollNo, password } = this.form.getRawValue();
    this.auth.login(rollNo.trim(), password).subscribe({
      next: () => {
        this.pending.set(false);
        void this.router.navigateByUrl(this.redirectTo());
      },
      error: (err: unknown) => {
        this.pending.set(false);
        this.error.set(
          apiErrorMessage(
            err,
            "Sign in failed. Check your roll number and password.",
          ),
        );
      },
    });
  }
}
