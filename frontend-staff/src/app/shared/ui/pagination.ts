import { Component, computed, input, output } from '@angular/core';

import { Button } from './button';

/**
 * Range readout and page steps for a list.
 *
 * Renders nothing when everything already fits on one page — a pager under a
 * five-row table is noise.
 */
@Component({
  selector: 'app-pagination',
  imports: [Button],
  template: `
    @if (total() > limit()) {
      <div class="flex items-center justify-between gap-4 px-4 py-2.5 text-[13px] text-ink-muted">
        <span>{{ from() }}–{{ to() }} of {{ total() }}</span>
        <div class="flex items-center gap-2">
          <button
            appButton
            variant="secondary"
            size="sm"
            type="button"
            [disabled]="offset() === 0"
            (click)="go.emit(offset() - limit())"
          >
            Previous
          </button>
          <button
            appButton
            variant="secondary"
            size="sm"
            type="button"
            [disabled]="to() >= total()"
            (click)="go.emit(offset() + limit())"
          >
            Next
          </button>
        </div>
      </div>
    }
  `,
  host: { class: 'block' },
})
export class Pagination {
  readonly total = input.required<number>();
  readonly limit = input.required<number>();
  readonly offset = input.required<number>();

  /** The new offset to load. */
  readonly go = output<number>();

  protected readonly from = computed(() => (this.total() ? this.offset() + 1 : 0));
  protected readonly to = computed(() => Math.min(this.offset() + this.limit(), this.total()));
}
