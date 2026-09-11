import { Component, computed, input } from '@angular/core';

export type BadgeTone = 'neutral' | 'accent' | 'ok' | 'warn' | 'danger';

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-sunken text-ink-muted',
  accent: 'bg-accent-soft text-accent',
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  danger: 'bg-danger-soft text-danger',
};

/**
 * A small state label.
 *
 * Tones map to the semantic tokens, so a register's present / leave / absent
 * read as the same three colours wherever they appear.
 */
@Component({
  selector: 'app-badge',
  template: `<ng-content />`,
  host: { '[class]': 'classes()' },
})
export class Badge {
  readonly tone = input<BadgeTone>('neutral');

  protected readonly classes = computed(() =>
    [
      'inline-flex items-center rounded-full px-2 py-0.5 text-[12px] font-medium whitespace-nowrap',
      TONES[this.tone()],
    ].join(' '),
  );
}
