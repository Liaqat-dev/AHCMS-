import { Component, inject } from '@angular/core';

import { ThemeService } from '../../core/theme.service';

/**
 * Light/dark switch.
 *
 * A single toggle rather than a three-way light/dark/system control: the
 * preference starts as `system` and following the OS is the default nobody has
 * to choose, so the control only has to offer the override.
 */
@Component({
  selector: 'app-theme-toggle',
  template: `
    <button
      type="button"
      class="flex h-9 w-9 items-center justify-center rounded-control border border-line
             bg-surface text-ink-muted transition-colors hover:bg-sunken hover:text-ink"
      [attr.aria-label]="
        theme.theme() === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
      "
      (click)="theme.toggle()"
    >
      @if (theme.theme() === 'dark') {
        <!-- sun -->
        <svg width="17" height="17" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <circle cx="10" cy="10" r="3.6" stroke="currentColor" stroke-width="1.5" />
          <path
            d="M10 1.5v2M10 16.5v2M18.5 10h-2M3.5 10h-2M16 4l-1.4 1.4M5.4 14.6L4 16M16 16l-1.4-1.4M5.4 5.4L4 4"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
          />
        </svg>
      } @else {
        <!-- moon -->
        <svg width="17" height="17" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M17 12.3A7.5 7.5 0 017.7 3 7.5 7.5 0 1017 12.3z"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linejoin="round"
          />
        </svg>
      }
    </button>
  `,
})
export class ThemeToggle {
  protected readonly theme = inject(ThemeService);
}
