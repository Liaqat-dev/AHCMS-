import { Component, ViewEncapsulation, booleanAttribute, computed, input } from '@angular/core';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-control font-medium ' +
  'whitespace-nowrap transition-colors duration-100 ' +
  'disabled:cursor-not-allowed disabled:opacity-45 ' +
  'aria-disabled:cursor-not-allowed aria-disabled:opacity-45';

const VARIANTS: Record<ButtonVariant, string> = {
  // The one filled thing on a page. Exactly one per view, ideally.
  primary: 'bg-accent text-on-accent hover:bg-accent-hover',
  // The workhorse: reads as a control because of its rule, not a fill.
  secondary: 'border border-line bg-surface text-ink hover:bg-sunken hover:border-line-strong',
  // For actions that sit inside dense rows, where a border would add noise.
  ghost: 'text-ink-muted hover:bg-sunken hover:text-ink',
  danger: 'bg-danger text-on-danger hover:brightness-95',
};

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-[13px]',
  md: 'h-10 px-4 text-[14px]',
  lg: 'h-11 px-5 text-[15px]',
};

/**
 * Button, as an attribute on a real `<button>` or `<a>`.
 *
 * An attribute rather than a wrapper element, so everything native keeps
 * working without being re-implemented: `type="submit"`, `disabled`, form
 * association, `routerLink`, middle-click on links, keyboard activation.
 *
 * ```html
 * <button appButton variant="primary" (click)="save()">Save changes</button>
 * <button appButton variant="secondary" size="sm" [loading]="saving()">Retry</button>
 * <a appButton variant="ghost" routerLink="/students">All students</a>
 * ```
 *
 * `loading` shows a spinner and blocks pointer input, but leaves the element
 * focusable and announces itself — a disabled button vanishes from the tab
 * order mid-interaction, which loses the keyboard user's place.
 */
@Component({
  selector: 'button[appButton], a[appButton]',
  encapsulation: ViewEncapsulation.None,
  template: `
    @if (loading()) {
      <span class="app-btn-spinner" aria-hidden="true"></span>
    }
    <ng-content />
  `,
  styles: `
    .app-btn-spinner {
      width: 0.875em;
      height: 0.875em;
      border: 2px solid currentColor;
      border-top-color: transparent;
      border-radius: 50%;
      animation: app-btn-spin 0.6s linear infinite;
      flex: none;
    }
    @keyframes app-btn-spin {
      to {
        transform: rotate(360deg);
      }
    }
  `,
  host: {
    '[class]': 'classes()',
    '[attr.aria-busy]': 'loading() || null',
    '[attr.aria-disabled]': 'loading() || null',
    // Native `disabled` is not available on <a>, and on <button> it would drop
    // the element out of the tab order while a request is in flight.
    '[style.pointer-events]': 'loading() ? "none" : null',
  },
})
export class Button {
  readonly variant = input<ButtonVariant>('secondary');
  readonly size = input<ButtonSize>('md');
  /** Stretch to the container — for a form's final action on narrow screens. */
  readonly block = input(false, { transform: booleanAttribute });
  readonly loading = input(false, { transform: booleanAttribute });

  protected readonly classes = computed(() =>
    [BASE, VARIANTS[this.variant()], SIZES[this.size()], this.block() ? 'w-full' : ''].join(' '),
  );
}
