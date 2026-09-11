/**
 * Class strings shared by form controls and tables.
 *
 * Constants rather than components: an `<input>` needs to stay an `<input>` so
 * `formControlName`, `type`, `autocomplete` and native validation keep working.
 * Only the appearance is shared.
 *
 * Whole class names, never interpolated — Tailwind reads source as text.
 */

const CONTROL_BASE =
  'w-full rounded-control border border-line bg-surface px-3 py-2 text-[14px] text-ink ' +
  'transition-colors placeholder:text-ink-faint hover:border-line-strong ' +
  'focus:border-accent focus:outline-none disabled:opacity-50';

export const INPUT = CONTROL_BASE;

/** Native arrow is kept: a custom one is one more thing to keep accessible. */
export const SELECT = CONTROL_BASE + ' pr-8';

export const LABEL = 'block text-[13px] font-medium text-ink';

/** A bordered panel that scrolls sideways rather than pushing the page wide. */
export const TABLE_WRAP = 'overflow-x-auto rounded-panel border border-line bg-surface';

export const TABLE = 'w-full border-collapse text-[14px]';

/** Column headings: quiet, and not shouting in capitals. */
export const TH =
  'border-b border-line bg-sunken px-4 py-2.5 text-left text-[12.5px] font-medium text-ink-muted';

export const TD = 'border-b border-line-soft px-4 py-2.5 align-middle';

/** Right-aligned for figures, so digits line up down the column. */
export const TD_NUM = TD + ' text-right';
export const TH_NUM = TH + ' text-right';
