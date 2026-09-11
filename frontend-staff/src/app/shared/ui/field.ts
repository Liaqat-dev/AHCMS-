import { Component, input } from '@angular/core';

/**
 * Label, control, and the message when the control is wrong.
 *
 * The control itself is projected, so it stays a native element with its own
 * `formControlName`, `type` and autocomplete intact.
 */
@Component({
  selector: 'app-field',
  template: `
    <label class="block text-[13px] font-medium text-ink" [attr.for]="for()">
      {{ label() }}
    </label>
    <div class="mt-1.5">
      <ng-content />
    </div>
    @if (error()) {
      <p class="mt-1 text-[12.5px] text-danger">{{ error() }}</p>
    } @else if (hint()) {
      <p class="mt-1 text-[12.5px] text-ink-muted">{{ hint() }}</p>
    }
  `,
  host: { class: 'block' },
})
export class Field {
  readonly label = input.required<string>();
  readonly for = input<string>();
  readonly hint = input<string>();
  readonly error = input<string | null>(null);
}
