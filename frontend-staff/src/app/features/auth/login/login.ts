import { Component, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { apiErrorMessage } from '../../../core/api-error';
import { AuthService } from '../../../core/auth/auth.service';
import { Button } from '../../../shared/ui/button';
import { ThemeToggle } from '../../../shared/ui/theme-toggle';

const FIELD =
  'mt-1.5 w-full rounded-control border border-line bg-surface px-3 py-2 text-[14.5px] ' +
  'text-ink transition-colors placeholder:text-ink-faint hover:border-line-strong ' +
  'focus:border-accent focus:outline-none';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, Button, ThemeToggle],
  template: `
    <div class="flex min-h-screen flex-col bg-canvas">
      <div class="flex justify-end p-4">
        <app-theme-toggle />
      </div>

      <div class="flex flex-1 items-start justify-center px-4 pb-24 sm:items-center sm:pb-32">
        <div class="w-full max-w-sm">
          <h1 class="font-display text-[28px] leading-tight text-ink">College MS</h1>
          <p class="mt-1 text-[14px] text-ink-muted">Staff sign in</p>

          <form class="mt-7 space-y-4" [formGroup]="form" (ngSubmit)="submit()">
            <div>
              <label class="block text-[13.5px] font-medium text-ink" for="email">Email</label>
              <input
                id="email"
                type="email"
                formControlName="email"
                autocomplete="username"
                [class]="field"
              />
            </div>

            <div>
              <label class="block text-[13.5px] font-medium text-ink" for="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                formControlName="password"
                autocomplete="current-password"
                [class]="field"
              />
            </div>

            @if (error()) {
              <p
                class="rounded-control border border-danger/25 bg-danger-soft px-3 py-2
                       text-[13.5px] text-danger"
                role="alert"
              >
                {{ error() }}
              </p>
            }

            <button
              appButton
              variant="primary"
              size="lg"
              block
              type="submit"
              [disabled]="form.invalid"
              [loading]="pending()"
            >
              {{ pending() ? 'Signing in' : 'Sign in' }}
            </button>
          </form>

          <p class="mt-8 border-t border-line pt-4 text-[13px] text-ink-muted">
            Students sign in with their roll number, on the student portal.
          </p>
        </div>
      </div>
    </div>
  `,
})
export class Login {
  /** Bound from the `redirectTo` query param by `withComponentInputBinding()`. */
  readonly redirectTo = input('/dashboard');

  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly field = FIELD;
  protected readonly pending = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    // Matches the backend's own minimum, so a too-short password fails here
    // rather than costing a round trip.
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  protected submit(): void {
    if (this.form.invalid || this.pending()) {
      return;
    }
    this.pending.set(true);
    this.error.set(null);

    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: () => {
        this.pending.set(false);
        void this.router.navigateByUrl(this.redirectTo());
      },
      error: (err: unknown) => {
        this.pending.set(false);
        this.error.set(apiErrorMessage(err, 'Sign in failed. Check your email and password.'));
      },
    });
  }
}
