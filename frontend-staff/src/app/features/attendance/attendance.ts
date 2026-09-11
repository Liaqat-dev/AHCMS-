import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';

import { apiErrorMessage } from '../../core/api-error';
import {
  AttendanceMark,
  AttendanceSheet,
  AttendanceStatus,
  AttendanceSummary,
  ClassRow,
  MarkInput,
} from '../../core/api/domain';
import { AttendanceApi, ClassesApi } from '../../core/api/services';
import { Permission } from '../../core/auth/permissions';
import { TokenService } from '../../core/auth/token.service';
import { ListState } from '../../shared/list-state';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT, SELECT, TABLE, TABLE_WRAP, TD, TH } from '../../shared/ui/controls';
import { Empty } from '../../shared/ui/empty';
import { PageHeader } from '../../shared/ui/page-header';
import { Pagination } from '../../shared/ui/pagination';

/** Marking states, in the order a register is read. */
const STATUSES: { value: AttendanceStatus; label: string; on: string }[] = [
  { value: 'present', label: 'Present', on: 'bg-ok-soft text-ok border-ok/40' },
  { value: 'absent', label: 'Absent', on: 'bg-danger-soft text-danger border-danger/40' },
  { value: 'leave', label: 'Leave', on: 'bg-warn-soft text-warn border-warn/40' },
];

const SEGMENT_BASE =
  'h-8 border-y border-r px-3 text-[13px] font-medium transition-colors first:rounded-l-control ' +
  'first:border-l last:rounded-r-control focus-visible:relative';
const SEGMENT_OFF = 'border-line bg-surface text-ink-muted hover:bg-sunken hover:text-ink';

/** The id of the register a 409 says is already there, if that is the conflict. */
function existingId(err: unknown): string | null {
  if (!(err instanceof HttpErrorResponse) || err.status !== 409) {
    return null;
  }
  const details = (err.error as { error?: { details?: { attendance_id?: string } } } | null)?.error
    ?.details;
  return details?.attendance_id ?? null;
}

/** Local date, so "today" is the user's own day rather than UTC's. */
function todayLocal(): string {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, '0');
  const day = `${now.getDate()}`.padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * Attendance — the daily register.
 *
 * The whole page is one task: pick a class, mark who is not there, save. So
 * the register itself is the page's body rather than something behind a link,
 * and the list of past registers sits underneath it.
 *
 * Marks are held locally and saved in one request. A teacher calling a roll
 * should not wait on the network between two names, and a half-sent register
 * is worse than an unsaved one.
 */
@Component({
  selector: 'app-attendance',
  imports: [Badge, Button, Empty, PageHeader, Pagination],
  template: `
    <div class="space-y-6">
      <app-page-header
        heading="Attendance"
        description="One register per class per day. A day with no register is a day the class did not meet."
      />

      <!-- Take the register -->
      <div class="rounded-panel border border-line bg-surface p-4">
        <div class="flex flex-wrap items-end gap-3">
          <div class="min-w-[13rem] flex-1">
            <label class="block text-[13px] font-medium text-ink" for="reg-class">Class</label>
            <select
              id="reg-class"
              [class]="select"
              class="mt-1.5"
              [value]="classId()"
              (change)="classId.set($any($event.target).value)"
            >
              <option value="">Choose a class</option>
              @for (row of classes(); track row.id) {
                <option [value]="row.id">{{ row.program_code }} · {{ row.name }}</option>
              }
            </select>
          </div>
          <div>
            <label class="block text-[13px] font-medium text-ink" for="reg-date">Date</label>
            <input
              id="reg-date"
              type="date"
              [class]="input"
              class="mt-1.5"
              [max]="today"
              [value]="date()"
              (change)="date.set($any($event.target).value)"
            />
          </div>
          @if (canOpen()) {
            <button
              appButton
              variant="primary"
              type="button"
              [disabled]="!classId()"
              [loading]="opening()"
              (click)="takeRegister()"
            >
              Take register
            </button>
          } @else {
            <button
              appButton
              variant="secondary"
              type="button"
              [disabled]="!classId()"
              [loading]="opening()"
              (click)="takeRegister()"
            >
              View register
            </button>
          }
        </div>
        @if (openError()) {
          <p class="mt-3 text-[13px] text-danger" role="alert">{{ openError() }}</p>
        }
      </div>

      <!-- The register -->
      @if (sheet(); as current) {
        <section class="rounded-panel border border-line bg-surface">
          <header
            class="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b
                   border-line px-5 py-3.5"
          >
            <div>
              <h2 class="text-[17px] leading-6">
                {{ current.class.name }}
                <span class="text-ink-muted">· {{ current.class.program_code }}</span>
              </h2>
              <p class="mt-0.5 text-[13px] text-ink-muted">{{ longDate(current.date) }}</p>
            </div>

            <!-- The tally is the register's own summary, so it lives in its
                 header and updates as marks change, before any save. -->
            <div class="flex flex-wrap items-center gap-2">
              <app-badge tone="ok">{{ tally().present }} present</app-badge>
              <app-badge tone="danger">{{ tally().absent }} absent</app-badge>
              <app-badge tone="warn">{{ tally().leave }} leave</app-badge>
              @if (tally().unmarked) {
                <app-badge tone="neutral">{{ tally().unmarked }} unmarked</app-badge>
              }
            </div>
          </header>

          @if (canMark()) {
            <div
              class="flex flex-wrap items-center justify-between gap-3 border-b border-line
                     bg-sunken px-5 py-2.5"
            >
              <button appButton variant="ghost" size="sm" type="button" (click)="markAllPresent()">
                Mark everyone present
              </button>
              <div class="flex items-center gap-3">
                @if (dirtyCount()) {
                  <span class="text-[13px] text-ink-muted">
                    {{ dirtyCount() }} unsaved {{ dirtyCount() === 1 ? 'change' : 'changes' }}
                  </span>
                }
                <button
                  appButton
                  variant="primary"
                  size="sm"
                  type="button"
                  [disabled]="!dirtyCount()"
                  [loading]="saving()"
                  (click)="save()"
                >
                  Save marks
                </button>
              </div>
            </div>
          }

          @if (saveError()) {
            <p class="border-b border-line px-5 py-2.5 text-[13px] text-danger" role="alert">
              {{ saveError() }}
            </p>
          }

          <ul class="divide-y divide-line-soft">
            @for (mark of current.marks; track mark.student.id) {
              <li class="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2.5">
                <span class="w-20 shrink-0 text-[13px] text-ink-muted">
                  {{ mark.student.roll_no }}
                </span>
                <span class="min-w-0 flex-1 text-[14.5px]">
                  {{ mark.student.first_name }} {{ mark.student.last_name }}
                  @if (mark.off_roster) {
                    <span class="ml-2 text-[12.5px] text-ink-faint">no longer in this class</span>
                  }
                </span>

                <div
                  class="flex items-center"
                  role="group"
                  [attr.aria-label]="'Mark ' + mark.student.roll_no"
                >
                  @for (status of statuses; track status.value) {
                    <button
                      type="button"
                      [disabled]="!canMark()"
                      [attr.aria-pressed]="marks().get(mark.student.id) === status.value"
                      [class]="
                        marks().get(mark.student.id) === status.value
                          ? segmentBase + ' ' + status.on
                          : segmentBase + ' ' + segmentOff
                      "
                      (click)="setMark(mark.student.id, status.value)"
                    >
                      {{ status.label }}
                    </button>
                  }
                </div>
              </li>
            } @empty {
              <app-empty
                heading="Nobody on this register"
                description="No student was enrolled in this class on this date."
              />
            }
          </ul>
        </section>
      }

      <!-- Past registers -->
      <section class="space-y-3">
        <h2 class="text-[17px]">Recent registers</h2>

        @if (list.error(); as message) {
          <p
            class="rounded-panel border border-danger/25 bg-danger-soft px-4 py-3 text-[14px] text-danger"
            role="alert"
          >
            {{ message }}
          </p>
        }

        <div [class]="tableWrap">
          @if (list.items().length) {
            <table [class]="table">
              <thead>
                <tr>
                  <th [class]="th" scope="col">Date</th>
                  <th [class]="th" scope="col">Class</th>
                  <th [class]="th" scope="col">Marked</th>
                  <th [class]="th" scope="col"><span class="sr-only">Open</span></th>
                </tr>
              </thead>
              <tbody>
                @for (row of list.items(); track row.id) {
                  <tr class="hover:bg-sunken">
                    <td [class]="td + ' whitespace-nowrap'">{{ row.date }}</td>
                    <td [class]="td">
                      <app-badge tone="accent">{{ row.class.program_code }}</app-badge>
                      <span class="ml-2">{{ row.class.name }}</span>
                    </td>
                    <td [class]="td">
                      <span class="text-ink-muted">
                        {{ row.counts.total - row.counts.unmarked }}/{{ row.counts.total }}
                      </span>
                      @if (row.counts.unmarked) {
                        <span class="ml-2 text-[12.5px] text-warn">
                          {{ row.counts.unmarked }} unmarked
                        </span>
                      }
                    </td>
                    <td [class]="td + ' text-right whitespace-nowrap'">
                      <button
                        appButton
                        variant="ghost"
                        size="sm"
                        type="button"
                        (click)="openSheet(row)"
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>

            <app-pagination
              [total]="list.total()"
              [limit]="list.limit"
              [offset]="list.offset()"
              (go)="list.goTo($event, reload)"
            />
          } @else if (list.loaded()) {
            <app-empty
              heading="No registers yet"
              description="Choose a class above and take the first one."
            />
          }
        </div>
      </section>
    </div>
  `,
})
export class Attendance {
  private readonly api = inject(AttendanceApi);
  private readonly classesApi = inject(ClassesApi);
  private readonly tokens = inject(TokenService);

  protected readonly input = INPUT;
  protected readonly select = SELECT;
  protected readonly table = TABLE;
  protected readonly tableWrap = TABLE_WRAP;
  protected readonly th = TH;
  protected readonly td = TD;
  protected readonly statuses = STATUSES;
  protected readonly segmentBase = SEGMENT_BASE;
  protected readonly segmentOff = SEGMENT_OFF;
  protected readonly today = todayLocal();

  protected readonly list = new ListState<AttendanceSummary>(10);
  protected readonly classes = signal<ClassRow[]>([]);
  /** Opening a register and marking it are separate grants from deleting one. */
  protected readonly canOpen = computed(() => this.tokens.has(Permission.AttendanceCreate));
  protected readonly canMark = computed(() => this.tokens.has(Permission.AttendanceUpdate));

  protected readonly classId = signal('');
  protected readonly date = signal(todayLocal());
  protected readonly sheet = signal<AttendanceSheet | null>(null);

  /** Working copy of the marks; saved as a diff against `original`. */
  protected readonly marks = signal<Map<string, AttendanceStatus | null>>(new Map());
  private original = new Map<string, AttendanceStatus | null>();

  protected readonly opening = signal(false);
  protected readonly saving = signal(false);
  protected readonly openError = signal<string | null>(null);
  protected readonly saveError = signal<string | null>(null);

  /** Live tally, from the working copy rather than the saved sheet. */
  protected readonly tally = computed(() => {
    const counts = { present: 0, absent: 0, leave: 0, unmarked: 0 };
    for (const status of this.marks().values()) {
      if (status) {
        counts[status] += 1;
      } else {
        counts.unmarked += 1;
      }
    }
    return counts;
  });

  protected readonly dirtyCount = computed(() => this.changed().length);

  protected readonly reload = (): void => {
    this.list.load(({ limit, offset }) => this.api.list({ limit, offset }));
  };

  constructor() {
    this.classesApi.list({ limit: 100 }).subscribe({
      next: (page) => this.classes.set(page.items),
      error: () => this.classes.set([]),
    });
    this.reload();
  }

  protected longDate(iso: string): string {
    return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  }

  /**
   * One action, whatever the state: open the register for this class and date,
   * or land on the one that already exists. The 409 carries the existing id,
   * so a clash is a redirect rather than an error to read and act on.
   */
  protected takeRegister(): void {
    const classId = this.classId();
    if (!classId || this.opening()) {
      return;
    }
    this.opening.set(true);
    this.openError.set(null);

    const existing = () =>
      this.api.forClassOn(classId, this.date()).subscribe({
        next: (sheet) => this.acceptSheet(sheet),
        error: (err: unknown) => this.failOpen(err),
      });

    if (!this.canOpen()) {
      existing();
      return;
    }

    this.api.open(classId, this.date()).subscribe({
      next: (sheet) => {
        this.acceptSheet(sheet);
        this.reload();
      },
      error: (err: unknown) => {
        // Two different conflicts answer 409 here: "a register already exists"
        // and "nobody was enrolled in this class on that date". Only the first
        // names an attendance_id, and only it should redirect to that
        // register — treating both alike showed a misleading "no register for
        // that date" for a class that simply has no students.
        if (existingId(err)) {
          existing();
          return;
        }
        this.failOpen(err);
      },
    });
  }

  protected openSheet(row: AttendanceSummary): void {
    this.opening.set(true);
    this.openError.set(null);
    this.classId.set(row.class.id);
    this.date.set(row.date);
    this.api.sheet(row.id).subscribe({
      next: (sheet) => this.acceptSheet(sheet),
      error: (err: unknown) => this.failOpen(err),
    });
  }

  protected setMark(studentId: string, status: AttendanceStatus): void {
    if (!this.canMark()) {
      return;
    }
    const next = new Map(this.marks());
    // Pressing the current state again clears it: unmarked is a real answer,
    // and it is the only way back to it.
    next.set(studentId, next.get(studentId) === status ? null : status);
    this.marks.set(next);
  }

  protected markAllPresent(): void {
    const next = new Map(this.marks());
    for (const [id, status] of next) {
      if (status === null) {
        next.set(id, 'present');
      }
    }
    this.marks.set(next);
  }

  protected save(): void {
    const current = this.sheet();
    const changes = this.changed();
    if (!current || !changes.length || this.saving()) {
      return;
    }
    this.saving.set(true);
    this.saveError.set(null);

    this.api.mark(current.id, changes).subscribe({
      next: (sheet) => {
        this.saving.set(false);
        this.acceptSheet(sheet);
        this.reload();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.saveError.set(apiErrorMessage(err, 'Could not save these marks.'));
      },
    });
  }

  /** Only the students whose mark differs from what is stored. */
  private changed(): MarkInput[] {
    const changes: MarkInput[] = [];
    for (const [studentId, status] of this.marks()) {
      if (this.original.get(studentId) !== status) {
        changes.push({ student_id: studentId, status });
      }
    }
    return changes;
  }

  private acceptSheet(sheet: AttendanceSheet): void {
    this.opening.set(false);
    this.sheet.set(sheet);
    const marks = new Map<string, AttendanceStatus | null>(
      sheet.marks.map((mark: AttendanceMark) => [mark.student.id, mark.status]),
    );
    this.marks.set(marks);
    this.original = new Map(marks);
  }

  private failOpen(err: unknown): void {
    this.opening.set(false);
    this.sheet.set(null);
    this.openError.set(
      err instanceof HttpErrorResponse && err.status === 404
        ? 'This class has no register for that date.'
        : apiErrorMessage(err, 'Could not open this register.'),
    );
  }
}
