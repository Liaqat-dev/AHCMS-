import {
  Component,
  ElementRef,
  ViewEncapsulation,
  booleanAttribute,
  computed,
  effect,
  input,
  output,
  viewChild,
} from '@angular/core';

export type ModalSize = 'sm' | 'md' | 'lg';

const SIZES: Record<ModalSize, string> = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-3xl',
};

/**
 * A modal dialog, built on the native `<dialog>` element.
 *
 * Native rather than a div with a z-index, because `showModal()` already does
 * the parts that are easy to get wrong: it traps focus, restores focus to the
 * trigger on close, closes on Escape, marks the rest of the page inert, and
 * renders in the top layer so no stacking context can bury it.
 *
 * ```html
 * <app-modal
 *   [open]="confirming()"
 *   heading="Delete this register?"
 *   description="The marks for 3 March go with it. This cannot be undone."
 *   (closed)="confirming.set(false)"
 * >
 *   <p>…</p>
 *   <button appButton variant="secondary" modal-actions (click)="confirming.set(false)">
 *     Keep register
 *   </button>
 *   <button appButton variant="danger" modal-actions (click)="remove()">Delete register</button>
 * </app-modal>
 * ```
 *
 * `closed` fires however the dialog was dismissed — Escape, the close button,
 * or the backdrop — so the caller has one place to reset its state.
 */
@Component({
  selector: 'app-modal',
  encapsulation: ViewEncapsulation.None,
  template: `
    <!-- The dialog and its panel are not controls, and their click handlers
         only implement backdrop dismissal. The keyboard equivalent the rule
         asks for is Escape, which <dialog> already provides. -->
    <!-- eslint-disable @angular-eslint/template/click-events-have-key-events -->
    <!-- eslint-disable @angular-eslint/template/interactive-supports-focus -->
    <dialog
      #dialog
      class="p-4 sm:p-6"
      [attr.aria-labelledby]="heading() ? headingId : null"
      [attr.aria-label]="heading() ? null : label()"
      (close)="closed.emit()"
      (cancel)="onCancel($event)"
      (click)="onBackdropClick($event)"
    >
      <!-- Stops a click that started inside the panel from reading as a
           backdrop click when the pointer is released outside it. -->
      <div class="app-modal-panel" [class]="panelSize()" (click)="$event.stopPropagation()">
        @if (heading() || dismissible()) {
          <header class="flex items-start gap-4 border-b border-line px-5 py-4">
            <div class="min-w-0 flex-1">
              @if (heading()) {
                <h2 [id]="headingId" class="text-[19px] leading-6 text-ink">{{ heading() }}</h2>
              }
              @if (description()) {
                <p class="mt-1 text-[13.5px] text-ink-muted">{{ description() }}</p>
              }
            </div>
            @if (dismissible()) {
              <button
                type="button"
                class="-mr-1 -mt-1 flex h-8 w-8 flex-none items-center justify-center
                       rounded-control text-ink-muted transition-colors hover:bg-sunken
                       hover:text-ink"
                aria-label="Close"
                (click)="close()"
              >
                <svg width="15" height="15" viewBox="0 0 15 15" aria-hidden="true">
                  <path
                    d="M1 1l13 13M14 1L1 14"
                    stroke="currentColor"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    fill="none"
                  />
                </svg>
              </button>
            }
          </header>
        }

        <div class="max-h-[70vh] overflow-y-auto px-5 py-4 text-[14.5px] text-ink">
          <ng-content />
        </div>

        @if (hasActions()) {
          <footer
            class="flex flex-wrap items-center justify-end gap-2 border-t border-line
                   bg-sunken px-5 py-3.5"
          >
            <ng-content select="[modal-actions]" />
          </footer>
        }
      </div>
    </dialog>
    <!-- eslint-enable @angular-eslint/template/interactive-supports-focus -->
    <!-- eslint-enable @angular-eslint/template/click-events-have-key-events -->
  `,
  styles: `
    app-modal dialog {
      padding: 0;
      border: 0;
      background: transparent;
      max-width: none;
      max-height: none;
      width: 100%;
      height: 100%;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    app-modal dialog::backdrop {
      background: var(--t-scrim);
    }
    app-modal dialog:not([open]) {
      display: none;
    }
    app-modal .app-modal-panel {
      width: 100%;
      background: var(--t-surface);
      color: var(--t-ink);
      border: 1px solid var(--t-line);
      border-radius: var(--radius-raised);
      box-shadow: var(--t-shadow-raised);
      overflow: hidden;
    }
    /* The one orchestrated motion in the app: it shows where the panel came
       from. Everything else stays still. */
    app-modal dialog[open] .app-modal-panel {
      animation: app-modal-in 160ms cubic-bezier(0.2, 0.8, 0.3, 1);
    }
    app-modal dialog[open]::backdrop {
      animation: app-modal-fade 160ms ease-out;
    }
    @keyframes app-modal-in {
      from {
        opacity: 0;
        transform: translateY(8px) scale(0.985);
      }
    }
    @keyframes app-modal-fade {
      from {
        opacity: 0;
      }
    }
  `,
})
export class Modal {
  readonly open = input(false, { transform: booleanAttribute });
  readonly heading = input<string>();
  readonly description = input<string>();
  readonly size = input<ModalSize>('md');
  /** Render the footer slot. See the same input on `Card` for why it is explicit. */
  readonly hasActions = input(false, { transform: booleanAttribute });
  /**
   * Whether Escape, the backdrop and the close button dismiss it. Turn off for
   * a step the person must answer — but then give them an action that does.
   */
  readonly dismissible = input(true, { transform: booleanAttribute });
  /** Accessible name when there is no visible heading. */
  readonly label = input('Dialog');

  readonly closed = output<void>();

  protected readonly headingId = `modal-${Math.random().toString(36).slice(2, 9)}`;

  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  // Whole class names, never built by interpolation: Tailwind reads the source
  // as text, so a class assembled at runtime is never generated.
  protected readonly panelSize = computed(() => SIZES[this.size()]);

  constructor() {
    effect(() => {
      const element = this.dialog().nativeElement;
      const shouldBeOpen = this.open();

      if (shouldBeOpen && !element.open) {
        element.showModal();
      } else if (!shouldBeOpen && element.open) {
        // `close()` fires the close event, which the caller is already
        // listening to; emitting again here would double up.
        element.close();
      }

      // showModal() makes the page inert but does not stop it scrolling behind
      // the dialog.
      element.ownerDocument.documentElement.style.overflow = shouldBeOpen ? 'hidden' : '';
    });
  }

  close(): void {
    this.dialog().nativeElement.close();
  }

  protected onCancel(event: Event): void {
    if (!this.dismissible()) {
      event.preventDefault();
    }
  }

  protected onBackdropClick(event: MouseEvent): void {
    // The panel stops its own clicks, so anything arriving here is the
    // backdrop.
    if (this.dismissible() && event.target === this.dialog().nativeElement) {
      this.close();
    }
  }
}
