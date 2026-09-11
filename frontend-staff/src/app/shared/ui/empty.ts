import { Component, input } from '@angular/core';

/**
 * What a section shows before it holds anything.
 *
 * An empty screen is an invitation to act, so it names the next step rather
 * than reporting that a list is empty.
 */
@Component({
  selector: 'app-empty',
  template: `
    <div class="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <p class="text-[15px] text-ink">{{ heading() }}</p>
      @if (description()) {
        <p class="measure text-[13.5px] text-ink-muted">{{ description() }}</p>
      }
      <div class="mt-1 flex items-center gap-2">
        <ng-content />
      </div>
    </div>
  `,
  host: { class: 'block' },
})
export class Empty {
  readonly heading = input.required<string>();
  readonly description = input<string>();
}
