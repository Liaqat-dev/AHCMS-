import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api-error';
import { Faculty as FacultyRow } from '../../core/api/domain';
import { FacultyApi } from '../../core/api/services';
import { Permission } from '../../core/auth/permissions';
import { TokenService } from '../../core/auth/token.service';
import { ListState, debounced } from '../../shared/list-state';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT, SELECT, TABLE, TABLE_WRAP, TD, TH } from '../../shared/ui/controls';
import { Empty } from '../../shared/ui/empty';
import { Modal } from '../../shared/ui/modal';
import { PageHeader } from '../../shared/ui/page-header';
import { Pagination } from '../../shared/ui/pagination';

/**
 * Faculty — the staff register.
 *
 * A personnel file behaves like an admission file: the employee number and a
 * name open it, the rest arrives later, and the list says what is still
 * outstanding. Someone who leaves is marked inactive rather than deleted, so
 * old records can still name them.
 *
 * The table sheds columns as the screen narrows rather than scrolling
 * sideways: on a phone the employee number, the name and whether they are
 * current are what a staff list is for, and a horizontal scrollbar hides
 * exactly the columns you cannot see are missing.
 *
 * Adding and editing happen on their own page (`faculty-form.ts`), matching
 * the student admission form — a personnel file is too much to put in a modal,
 * and a URL per record means one can be linked to.
 */
@Component({
  selector: 'app-faculty',
  imports: [RouterLink, Badge, Button, Empty, Modal, PageHeader, Pagination],
  template: `
    <div class="space-y-6">
      <app-page-header
        heading="Faculty"
        description="Teaching and support staff. Separate from sign-in accounts: someone can teach without ever using the system."
      >
        @if (canCreate()) {
          <a appButton variant="primary" actions routerLink="/faculty/new">Add faculty</a>
        }
      </app-page-header>

      <div class="flex flex-wrap items-center gap-3">
        <select
          [class]="select"
          class="max-w-[10rem]"
          aria-label="Filter by status"
          (change)="filterStatus($any($event.target).value)"
        >
          <option value="">Everyone</option>
          <option value="true">Current</option>
          <option value="false">Former</option>
        </select>
        <input
          type="search"
          [class]="input"
          class="max-w-xs"
          placeholder="Search name, employee no or role"
          aria-label="Search faculty"
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
                <th [class]="th" scope="col">Employee no</th>
                <th [class]="th" scope="col">Name</th>
                <th [class]="th + ' hidden sm:table-cell'" scope="col">Designation</th>
                <th [class]="th + ' hidden lg:table-cell'" scope="col">Contact</th>
                <th [class]="th + ' hidden md:table-cell'" scope="col">File</th>
                @if (canAct()) {
                  <th [class]="th" scope="col"><span class="sr-only">Actions</span></th>
                }
              </tr>
            </thead>
            <tbody>
              @for (member of list.items(); track member.id) {
                <tr class="hover:bg-sunken">
                  <td [class]="td + ' whitespace-nowrap'">{{ member.employee_no }}</td>
                  <td [class]="td">
                    {{ member.full_name }}
                    @if (!member.is_active) {
                      <app-badge tone="neutral" class="ml-2">Former</app-badge>
                    }
                    <!-- The designation still shows on a phone, where its own
                         column is gone, because it is how staff are told apart. -->
                    @if (member.designation) {
                      <span class="block text-[12.5px] text-ink-muted sm:hidden">
                        {{ member.designation }}
                      </span>
                    }
                  </td>
                  <td [class]="td + ' hidden sm:table-cell text-ink-muted'">
                    {{ member.designation ?? '—' }}
                  </td>
                  <td [class]="td + ' hidden lg:table-cell text-ink-muted whitespace-nowrap'">
                    {{ member.cell_no ?? member.email ?? '—' }}
                  </td>
                  <td [class]="td + ' hidden md:table-cell'">
                    @if (member.missing_fields.length) {
                      <app-badge tone="warn"
                        >{{ member.missing_fields.length }} outstanding</app-badge
                      >
                    } @else {
                      <app-badge tone="ok">Complete</app-badge>
                    }
                  </td>
                  @if (canAct()) {
                    <td [class]="td + ' text-right whitespace-nowrap'">
                      @if (canUpdate()) {
                        <a
                          appButton
                          variant="ghost"
                          size="sm"
                          [routerLink]="['/faculty', member.id, 'edit']"
                        >
                          Edit
                        </a>
                      }
                      @if (canDelete()) {
                        <button
                          appButton
                          variant="ghost"
                          size="sm"
                          type="button"
                          class="hidden sm:inline-flex"
                          (click)="confirm.set(member)"
                        >
                          Delete
                        </button>
                      }
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
            heading="No faculty yet"
            description="The register of teaching and support staff. An employee number and a name are enough to open a file."
          >
            @if (canCreate()) {
              <a appButton variant="primary" routerLink="/faculty/new">Add faculty</a>
            }
          </app-empty>
        }
      </div>
    </div>

    <app-modal
      [open]="confirm() !== null"
      size="sm"
      heading="Delete this record?"
      [description]="confirm() ? confirm()!.full_name + ' · ' + confirm()!.employee_no : ''"
      hasActions
      (closed)="confirm.set(null)"
    >
      <p class="measure">
        Marking them as former staff is usually better — it keeps their name on the records they
        already appear on. Deleting removes the file outright.
      </p>
      @if (deleteError()) {
        <p class="mt-3 text-[13px] text-danger" role="alert">{{ deleteError() }}</p>
      }

      <button appButton variant="secondary" modal-actions type="button" (click)="confirm.set(null)">
        Keep record
      </button>
      <button
        appButton
        variant="danger"
        modal-actions
        type="button"
        [loading]="deleting()"
        (click)="remove()"
      >
        Delete record
      </button>
    </app-modal>
  `,
})
export class Faculty {
  private readonly api = inject(FacultyApi);
  private readonly tokens = inject(TokenService);

  protected readonly input = INPUT;
  protected readonly select = SELECT;
  protected readonly table = TABLE;
  protected readonly tableWrap = TABLE_WRAP;
  protected readonly th = TH;
  protected readonly td = TD;

  protected readonly list = new ListState<FacultyRow>();
  protected readonly canCreate = computed(() => this.tokens.has(Permission.FacultyCreate));
  protected readonly canUpdate = computed(() => this.tokens.has(Permission.FacultyUpdate));
  protected readonly canDelete = computed(() => this.tokens.has(Permission.FacultyDelete));
  /** The actions column is only worth a column if either action is available. */
  protected readonly canAct = computed(() => this.canUpdate() || this.canDelete());

  protected readonly confirm = signal<FacultyRow | null>(null);
  protected readonly deleting = signal(false);
  protected readonly deleteError = signal<string | null>(null);

  private query = '';
  private status = '';

  protected readonly reload = (): void => {
    this.list.load(({ limit, offset }) =>
      this.api.list({ limit, offset, q: this.query, is_active: this.status }),
    );
  };

  private readonly runSearch = debounced<string>(250, (value) => {
    this.query = value;
    this.list.reset();
    this.reload();
  });

  constructor() {
    this.reload();
  }

  protected search(value: string): void {
    this.runSearch(value);
  }

  protected filterStatus(value: string): void {
    this.status = value;
    this.list.reset();
    this.reload();
  }

  protected remove(): void {
    const member = this.confirm();
    if (!member || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.deleteError.set(null);

    this.api.remove(member.id).subscribe({
      next: () => {
        this.deleting.set(false);
        this.confirm.set(null);
        this.list.offset.set(this.list.offsetAfterDelete());
        this.reload();
      },
      error: (err: unknown) => {
        this.deleting.set(false);
        this.deleteError.set(apiErrorMessage(err, 'Could not delete this record.'));
      },
    });
  }
}
