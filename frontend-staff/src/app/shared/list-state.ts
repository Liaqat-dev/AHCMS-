import { signal } from '@angular/core';
import { Observable } from 'rxjs';

import { apiErrorMessage } from '../core/api-error';
import { Page } from '../core/models/api';

/**
 * The state every list page keeps: rows, total, page window, and whether the
 * last load is still running or failed.
 *
 * Stale responses are dropped by sequence number. Typing in a search box fires
 * a request per keystroke-burst, and without this the slowest one to come back
 * wins and the table shows results for a query the person has already changed.
 */
export class ListState<T> {
  readonly items = signal<T[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  /** True once a load has completed, so "empty" is not shown before the first. */
  readonly loaded = signal(false);

  private sequence = 0;

  constructor(readonly limit = 20) {}

  load(source: (query: { limit: number; offset: number }) => Observable<Page<T>>): void {
    const ticket = ++this.sequence;
    this.loading.set(true);
    this.error.set(null);

    source({ limit: this.limit, offset: this.offset() }).subscribe({
      next: (page) => {
        if (ticket !== this.sequence) {
          return;
        }
        this.items.set(page.items);
        this.total.set(page.total);
        this.loading.set(false);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        if (ticket !== this.sequence) {
          return;
        }
        this.error.set(apiErrorMessage(err, 'Could not load this list.'));
        this.loading.set(false);
        this.loaded.set(true);
      },
    });
  }

  /** Jump to an offset and reload through `reload`. */
  goTo(offset: number, reload: () => void): void {
    this.offset.set(Math.max(0, offset));
    reload();
  }

  /** Back to the first page — for when a filter changes. */
  reset(): void {
    this.offset.set(0);
  }

  /**
   * After deleting the last row on a page, step back rather than showing an
   * empty final page.
   */
  offsetAfterDelete(): number {
    return this.items().length === 1 && this.offset() > 0
      ? this.offset() - this.limit
      : this.offset();
  }
}

/** Trailing debounce for search boxes. */
export function debounced<T>(wait: number, run: (value: T) => void): (value: T) => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return (value: T) => {
    clearTimeout(timer);
    timer = setTimeout(() => run(value), wait);
  };
}
