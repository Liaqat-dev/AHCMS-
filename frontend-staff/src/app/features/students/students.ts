import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api-error';
import { SessionRow, Student } from '../../core/api/domain';
import { SessionsApi, StudentsApi } from '../../core/api/services';
import { Permission } from '../../core/auth/permissions';
import { TokenService } from '../../core/auth/token.service';
import { ListState, debounced } from '../../shared/list-state';
import { Avatar } from '../../shared/ui/avatar';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT, SELECT, TABLE, TABLE_WRAP, TD, TH } from '../../shared/ui/controls';
import { Empty } from '../../shared/ui/empty';
import { Modal } from '../../shared/ui/modal';
import { PageHeader } from '../../shared/ui/page-header';
import { Pagination } from '../../shared/ui/pagination';

/**
 * Students — the admission register.
 *
 * The roll number leads the row because it is what the office quotes, and the
 * outstanding-fields count is a column rather than something to discover on
 * opening a record: a file half-filled is the normal state here, and the list
 * is where you notice which ones still need chasing.
 *
 * **A student is never deleted.** There is no `students:delete` code and no
 * DELETE endpoint — a file is closed by clearing `is_active`, so the roll
 * number stays allocated and the registers the student already appears on keep
 * naming somebody. The row action says "Deactivate" because that is what it
 * does, and it is reversible from the same place.
 */
@Component({
  selector: 'app-students',
  imports: [RouterLink, Avatar, Badge, Button, Empty, Modal, PageHeader, Pagination],
  template: `
    <div class="space-y-6">
      <app-page-header
        heading="Students"
        description="Opened at admission with a name and an intake; the rest of the file arrives over the following weeks."
      >
        @if (canCreate()) {
          <a appButton variant="primary" actions routerLink="/students/new">Add student</a>
        }
      </app-page-header>

      <div class="flex flex-wrap items-center gap-3">
        <select
          [class]="select"
          class="max-w-[11rem]"
          aria-label="Filter by intake"
          (change)="filterSession($any($event.target).value)"
        >
          <option value="">All intakes</option>
          @for (session of sessions(); track session.id) {
            <option [value]="session.id">{{ session.label }}</option>
          }
        </select>
        <input
          type="search"
          [class]="input"
          class="max-w-xs"
          placeholder="Search roll no, name or CNIC"
          aria-label="Search students"
          (input)="search($any($event.target).value)"
        />
        @if (list.loading()) {
          <span class="text-[13px] text-ink-muted">Loading…</span>
        }
      </div>

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
                <th [class]="th" scope="col">Roll no</th>
                <th [class]="th" scope="col">Student</th>
                <th [class]="th + ' hidden md:table-cell'" scope="col">Class</th>
                <th [class]="th + ' hidden lg:table-cell'" scope="col">Intake</th>
                <th [class]="th + ' hidden lg:table-cell'" scope="col">Contact</th>
                <th [class]="th + ' hidden sm:table-cell'" scope="col">File</th>
                @if (canUpdate()) {
                  <th [class]="th" scope="col"><span class="sr-only">Actions</span></th>
                }
              </tr>
            </thead>
            <tbody>
              @for (student of list.items(); track student.id) {
                <tr class="hover:bg-sunken">
                  <td [class]="td + ' whitespace-nowrap font-medium'">{{ student.roll_no }}</td>
                  <td [class]="td">
                    <div class="flex items-center gap-3">
                      <app-avatar [name]="student.full_name" [muted]="!student.is_active" />
                      <div class="min-w-0">
                        <div class="flex flex-wrap items-center gap-2">
                          <span class="truncate">{{ student.full_name }}</span>
                          @if (!student.is_active) {
                            <app-badge tone="neutral">Inactive</app-badge>
                          }
                        </div>
                        <!-- The father's name is how two students of the same
                             name are told apart on a register here, so it sits
                             under the name rather than in a column of its own. -->
                        <span class="block truncate text-[12.5px] text-ink-muted">
                          {{ student.father_name ?? student.b_form_cnic ?? '—' }}
                        </span>
                        <!-- The class still shows on a phone, where its own
                             column is gone: it is the other thing you scan for. -->
                        @if (student.enrollment; as enrollment) {
                          <span class="block text-[12.5px] text-ink-muted md:hidden">
                            {{ enrollment.program_code }} · {{ enrollment.class_name }}
                          </span>
                        }
                      </div>
                    </div>
                  </td>
                  <td [class]="td + ' hidden md:table-cell'">
                    @if (student.enrollment; as enrollment) {
                      <app-badge tone="accent">{{ enrollment.program_code }}</app-badge>
                      <span class="ml-2">{{ enrollment.class_name }}</span>
                    } @else {
                      <span class="text-ink-faint">Not enrolled</span>
                    }
                  </td>
                  <td [class]="td + ' hidden lg:table-cell text-ink-muted whitespace-nowrap'">
                    {{ student.session.label }}
                  </td>
                  <td [class]="td + ' hidden lg:table-cell text-ink-muted whitespace-nowrap'">
                    {{ student.cell_no ?? student.guardian_cell_no ?? student.email ?? '—' }}
                  </td>
                  <td [class]="td + ' hidden sm:table-cell'">
                    @if (student.missing_fields.length) {
                      <app-badge tone="warn">
                        {{ student.missing_fields.length }} outstanding
                      </app-badge>
                    } @else {
                      <app-badge tone="ok">Complete</app-badge>
                    }
                  </td>
                  @if (canUpdate()) {
                    <td [class]="td + ' text-right whitespace-nowrap'">
                      <a
                        appButton
                        variant="ghost"
                        size="sm"
                        [routerLink]="['/students', student.id, 'edit']"
                      >
                        Edit
                      </a>
                      <button
                        appButton
                        variant="ghost"
                        size="sm"
                        type="button"
                        class="hidden sm:inline-flex"
                        (click)="ask(student)"
                      >
                        {{ student.is_active ? 'Deactivate' : 'Restore' }}
                      </button>
                    </td>
                  }
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
            [heading]="sessions().length ? 'No students yet' : 'Add an intake first'"
            [description]="
              sessions().length
                ? 'Admission opens a file with a name and an intake; a roll number is allocated on the spot.'
                : 'A student belongs to an intake session, and none exists yet.'
            "
          >
            @if (canCreate() && sessions().length) {
              <a appButton variant="primary" routerLink="/students/new">Add student</a>
            }
          </app-empty>
        }
      </div>
    </div>

    <app-modal
      [open]="confirm() !== null"
      size="sm"
      [heading]="confirm()?.is_active ? 'Close this file?' : 'Reopen this file?'"
      [description]="confirm() ? confirm()!.full_name + ' · ' + confirm()!.roll_no : ''"
      hasActions
      (closed)="confirm.set(null)"
    >
      <p class="measure">
        @if (confirm()?.is_active) {
          The record is kept and the roll number stays theirs — a student is never deleted, because
          the registers and mark sheets they already appear on have to keep naming somebody. They
          lose portal sign-in, and this can be undone from the same place.
        } @else {
          The file reopens as it was left, with its roll number, enrollment and marks intact.
        }
      </p>
      @if (actionError()) {
        <p class="mt-3 text-[13px] text-danger" role="alert">{{ actionError() }}</p>
      }

      <button appButton variant="secondary" modal-actions type="button" (click)="confirm.set(null)">
        Cancel
      </button>
      <button
        appButton
        [variant]="confirm()?.is_active ? 'danger' : 'primary'"
        modal-actions
        type="button"
        [loading]="working()"
        (click)="setActive()"
      >
        {{ confirm()?.is_active ? 'Deactivate' : 'Restore' }}
      </button>
    </app-modal>
  `,
})
export class Students {
  private readonly api = inject(StudentsApi);
  private readonly sessionsApi = inject(SessionsApi);
  private readonly tokens = inject(TokenService);

  protected readonly input = INPUT;
  protected readonly select = SELECT;
  protected readonly table = TABLE;
  protected readonly tableWrap = TABLE_WRAP;
  protected readonly th = TH;
  protected readonly td = TD;

  protected readonly list = new ListState<Student>();
  protected readonly sessions = signal<SessionRow[]>([]);
  protected readonly canCreate = computed(() => this.tokens.has(Permission.StudentsCreate));
  protected readonly canUpdate = computed(() => this.tokens.has(Permission.StudentsUpdate));

  /** The row whose file is being closed or reopened, held for the dialog. */
  protected readonly confirm = signal<Student | null>(null);
  protected readonly working = signal(false);
  protected readonly actionError = signal<string | null>(null);

  private query = '';
  private sessionId = '';

  protected readonly reload = (): void => {
    this.list.load(({ limit, offset }) =>
      this.api.list({ limit, offset, q: this.query, session_id: this.sessionId }),
    );
  };

  private readonly runSearch = debounced<string>(250, (value) => {
    this.query = value;
    this.list.reset();
    this.reload();
  });

  constructor() {
    this.sessionsApi.list({ limit: 100 }).subscribe({
      next: (page) => this.sessions.set(page.items),
      error: () => this.sessions.set([]),
    });
    this.reload();
  }

  protected search(value: string): void {
    this.runSearch(value);
  }

  protected filterSession(value: string): void {
    this.sessionId = value;
    this.list.reset();
    this.reload();
  }

  protected ask(student: Student): void {
    this.actionError.set(null);
    this.confirm.set(student);
  }

  /**
   * Close or reopen the file.
   *
   * The row is replaced in place rather than reloading the list: it may be
   * filtered and paged, and a reload would shift rows under the cursor for a
   * change that affects exactly one of them.
   */
  protected setActive(): void {
    const student = this.confirm();
    if (!student || this.working()) {
      return;
    }
    this.working.set(true);
    this.actionError.set(null);
    this.api.update(student.id, { is_active: !student.is_active }).subscribe({
      next: (fresh) => {
        this.working.set(false);
        this.confirm.set(null);
        this.list.items.set(this.list.items().map((row) => (row.id === fresh.id ? fresh : row)));
      },
      error: (err: unknown) => {
        this.working.set(false);
        this.actionError.set(apiErrorMessage(err, 'Could not change this file.'));
      },
    });
  }
}
