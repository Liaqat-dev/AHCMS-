import { Component, signal } from '@angular/core';

import { Button } from '../../shared/ui/button';
import { Card } from '../../shared/ui/card';
import { Modal } from '../../shared/ui/modal';

/**
 * Placeholder dashboard.
 *
 * The figures below are stand-ins, marked as such — the real ones arrive when
 * the summary endpoints do. It is wired up with the shared Card, Button and
 * Modal so the primitives are exercised somewhere real rather than in a
 * gallery page nobody ships.
 */
@Component({
  selector: 'app-dashboard',
  imports: [Button, Card, Modal],
  template: `
    <div class="space-y-7">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="text-[26px] leading-tight">Today</h1>
          <p class="mt-0.5 text-[14px] text-ink-muted">Monday, 8 September</p>
        </div>
        <button appButton variant="primary" type="button" (click)="confirming.set(true)">
          Open a register
        </button>
      </header>

      <div class="grid gap-5 lg:grid-cols-3">
        <!-- Records read as ruled rows, not as one card per fact. -->
        <app-card
          class="lg:col-span-2"
          heading="Registers today"
          description="Classes that have met so far"
          flush
        >
          <button appButton variant="ghost" size="sm" card-actions type="button">View all</button>

          <ul class="divide-y divide-line">
            @for (row of registers; track row.class) {
              <li class="flex items-center gap-4 px-5 py-3">
                <span class="w-11 text-[12.5px] text-ink-muted">{{ row.code }}</span>
                <span class="flex-1 text-[14.5px]">{{ row.class }}</span>
                <span class="text-[13.5px] text-ink-muted">{{ row.marked }}/{{ row.total }}</span>
                <span [class]="row.done ? doneChip : openChip">
                  {{ row.done ? 'Complete' : 'In progress' }}
                </span>
              </li>
            } @empty {
              <li class="px-5 py-8 text-center text-[14px] text-ink-muted">
                No class has met yet today.
              </li>
            }
          </ul>
        </app-card>

        <app-card variant="inset" heading="Attendance this week">
          <p class="font-display text-[40px] leading-none text-ink">
            91.4<span class="text-[24px] text-ink-muted">%</span>
          </p>
          <p class="mt-1.5 text-[13.5px] text-ink-muted">
            Across 14 registers. Leave is excluded from the count.
          </p>
          <p class="mt-4 border-t border-line pt-3 text-[12.5px] text-ink-faint">
            Placeholder figure — the summary endpoints are not built yet.
          </p>
        </app-card>
      </div>
    </div>

    <app-modal
      [open]="confirming()"
      heading="Open a register?"
      description="This starts today's register for 1st Year (ENG). Every student begins unmarked."
      hasActions
      (closed)="confirming.set(false)"
    >
      <p class="measure">
        You can mark students now or come back later — the register stays editable. Only one
        register exists per class per day, so opening it twice is not possible.
      </p>

      <button
        appButton
        variant="secondary"
        modal-actions
        type="button"
        (click)="confirming.set(false)"
      >
        Cancel
      </button>
      <button appButton variant="primary" modal-actions type="button" (click)="open()">
        Open register
      </button>
    </app-modal>
  `,
})
export class Dashboard {
  protected readonly confirming = signal(false);

  protected readonly doneChip =
    'rounded-full bg-ok-soft px-2 py-0.5 text-[12px] font-medium text-ok';
  protected readonly openChip =
    'rounded-full bg-warn-soft px-2 py-0.5 text-[12px] font-medium text-warn';

  /** Stand-in rows until the summary endpoints exist. */
  protected readonly registers = [
    { code: 'ENG', class: '1st Year', marked: 38, total: 38, done: true },
    { code: 'ENG', class: '2nd Year', marked: 12, total: 34, done: false },
    { code: 'MED', class: '1st Year', marked: 41, total: 41, done: true },
  ];

  protected open(): void {
    this.confirming.set(false);
  }
}
