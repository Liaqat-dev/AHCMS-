import { Component, input } from '@angular/core';

/**
 * The title block every section opens with: what this page is, and the one or
 * two actions that belong to the page rather than to a row.
 */
@Component({
  selector: 'app-page-header',
  template: `
    <div class="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div class="min-w-0">
        <h1 class="text-[26px] leading-tight">{{ heading() }}</h1>
        @if (description()) {
          <p class="measure mt-1 text-[14px] text-ink-muted">{{ description() }}</p>
        }
      </div>
      <div class="flex flex-none items-center gap-2">
        <ng-content select="[actions]" />
      </div>
    </div>
  `,
  host: { class: 'block' },
})
export class PageHeader {
  readonly heading = input.required<string>();
  readonly description = input<string>();
}
