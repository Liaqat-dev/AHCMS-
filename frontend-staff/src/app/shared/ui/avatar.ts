import { Component, computed, input } from '@angular/core';

/**
 * A person, as a circle.
 *
 * Initials rather than a photograph: there is no attachments endpoint, so a
 * file has no picture to show, and a name-derived disc still does the job the
 * avatar is here for — giving the eye something to scan a long register by.
 *
 * The one thing it says with colour is whether the record is live. An inactive
 * student is not a different kind of person, so the disc goes quiet rather
 * than taking a second accent, and the tone stays semantic in the way every
 * other tone in the app is.
 */
@Component({
  selector: 'app-avatar',
  template: `{{ initials() }}`,
  host: {
    '[class]': 'classes()',
    '[attr.title]': 'name()',
    'aria-hidden': 'true',
  },
})
export class Avatar {
  readonly name = input('');
  /** The record is inactive; the disc reads as dormant, not as an alarm. */
  readonly muted = input(false);

  /**
   * First and last initial — "Ali Raza Khan" is AK, not AR.
   *
   * A single-word name gives one letter; an empty one gives none, and the
   * empty disc is still better than a placeholder glyph pretending to be one.
   */
  protected readonly initials = computed(() => {
    const parts = this.name().trim().split(/\s+/).filter(Boolean);
    if (!parts.length) {
      return '';
    }
    const first = parts[0][0];
    const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
    return (first + last).toUpperCase();
  });

  protected readonly classes = computed(() =>
    [
      'inline-flex h-9 w-9 flex-none select-none items-center justify-center rounded-full',
      'text-[12.5px] font-medium uppercase',
      this.muted() ? 'bg-sunken text-ink-faint' : 'bg-accent-soft text-accent',
    ].join(' '),
  );
}
