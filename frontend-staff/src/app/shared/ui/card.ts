import { Component, booleanAttribute, computed, input } from '@angular/core';

export type CardVariant = 'panel' | 'quiet' | 'inset';

const VARIANTS: Record<CardVariant, string> = {
  // The default: a bordered panel on the page. No shadow — it does not float.
  panel: 'border border-line bg-surface',
  // For a group that needs edges but not a second surface colour.
  quiet: 'border border-line bg-transparent',
  // Recessed: summaries, totals, an aside inside a panel.
  inset: 'border border-line bg-sunken',
};

/**
 * A bordered panel with optional header and footer.
 *
 * Deliberately not the container for everything. Records belong in ruled rows;
 * a card is for something that genuinely is a separate object — a form, a
 * summary, a group of controls. Chopping a page into identical cards is how
 * hierarchy gets flattened.
 *
 * No shadow in any variant. The modal is the only element in this app that
 * leaves the page, so it is the only one that casts one.
 *
 * ```html
 * <app-card heading="Today's registers" description="Classes that have met">
 *   <button appButton size="sm" card-actions>Open register</button>
 *   <ul>…</ul>
 *   <p card-footer>Updated a minute ago</p>
 * </app-card>
 * ```
 *
 * `flush` removes body padding, for a table or list that should meet the
 * card's edges.
 */
@Component({
  selector: 'app-card',
  template: `
    @if (heading() || description()) {
      <header
        class="flex items-start justify-between gap-4 border-b border-line px-5 py-3.5"
        [class.border-b]="!!heading() || !!description()"
      >
        <div class="min-w-0">
          @if (heading()) {
            <h2 class="truncate text-[17px] leading-6 text-ink">{{ heading() }}</h2>
          }
          @if (description()) {
            <p class="mt-0.5 text-[13px] text-ink-muted">{{ description() }}</p>
          }
        </div>
        <div class="flex flex-none items-center gap-2">
          <ng-content select="[card-actions]" />
        </div>
      </header>
    }

    <div [class]="bodyClasses()">
      <ng-content />
    </div>

    @if (hasFooter()) {
      <footer class="border-t border-line bg-sunken px-5 py-3 text-[13px] text-ink-muted">
        <ng-content select="[card-footer]" />
      </footer>
    }
  `,
  host: { '[class]': 'classes()' },
})
export class Card {
  readonly heading = input<string>();
  readonly description = input<string>();
  readonly variant = input<CardVariant>('panel');
  /** Drop the body padding so a table or list can meet the card's edges. */
  readonly flush = input(false, { transform: booleanAttribute });
  /**
   * Render the footer slot. Explicit because Angular cannot tell whether
   * projected content exists without reaching into the DOM, and a footer that
   * renders its border with nothing in it looks like a bug.
   */
  readonly hasFooter = input(false, { transform: booleanAttribute });

  protected readonly classes = computed(() =>
    ['block overflow-hidden rounded-panel', VARIANTS[this.variant()]].join(' '),
  );

  protected readonly bodyClasses = computed(() => (this.flush() ? '' : 'px-5 py-4'));
}
