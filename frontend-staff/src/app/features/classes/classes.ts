import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { apiErrorMessage } from '../../core/api-error';
import { ClassRow, Program } from '../../core/api/domain';
import { ClassesApi, ProgramsApi } from '../../core/api/services';
import { Permission } from '../../core/auth/permissions';
import { TokenService } from '../../core/auth/token.service';
import { ListState, debounced } from '../../shared/list-state';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT, SELECT, TABLE, TABLE_WRAP, TD, TH } from '../../shared/ui/controls';
import { Empty } from '../../shared/ui/empty';
import { Field } from '../../shared/ui/field';
import { Modal } from '../../shared/ui/modal';
import { PageHeader } from '../../shared/ui/page-header';
import { Pagination } from '../../shared/ui/pagination';

/**
 * Classes — the teaching groups inside a program.
 *
 * A class name is only unique within its program, so the program travels with
 * the name everywhere it appears: two "1st Year" rows are not a mistake.
 */
@Component({
  selector: 'app-classes',
  imports: [ReactiveFormsModule, Badge, Button, Empty, Field, Modal, PageHeader, Pagination],
  template: `
    <div class="space-y-6">
      <app-page-header
        heading="Classes"
        description="A teaching group inside a program. Names repeat across programs, so the code travels with them."
      >
        @if (canCreate()) {
          <button
            appButton
            variant="primary"
            type="button"
            actions
            [disabled]="!programs().length"
            (click)="startCreate()"
          >
            New class
          </button>
        }
      </app-page-header>

      <div class="flex flex-wrap items-center gap-3">
        <select
          [class]="select"
          class="max-w-[13rem]"
          aria-label="Filter by program"
          (change)="filterProgram($any($event.target).value)"
        >
          <option value="">All programs</option>
          @for (program of programs(); track program.id) {
            <option [value]="program.id">{{ program.code }} · {{ program.name }}</option>
          }
        </select>
        <input
          type="search"
          [class]="input"
          class="max-w-xs"
          placeholder="Search class name"
          aria-label="Search classes"
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
                <th [class]="th" scope="col">Program</th>
                <th [class]="th" scope="col">Class</th>
                @if (canAct()) {
                  <th [class]="th" scope="col"><span class="sr-only">Actions</span></th>
                }
              </tr>
            </thead>
            <tbody>
              @for (row of list.items(); track row.id) {
                <tr class="hover:bg-sunken">
                  <td [class]="td">
                    <app-badge tone="accent">{{ row.program_code }}</app-badge>
                    <span class="ml-2 text-ink-muted">{{ row.program_name }}</span>
                  </td>
                  <td [class]="td">{{ row.name }}</td>
                  @if (canAct()) {
                    <td [class]="td + ' text-right whitespace-nowrap'">
                      @if (canUpdate()) {
                        <button
                          appButton
                          variant="ghost"
                          size="sm"
                          type="button"
                          (click)="startEdit(row)"
                        >
                          Edit
                        </button>
                      }
                      @if (canDelete()) {
                        <button
                          appButton
                          variant="ghost"
                          size="sm"
                          type="button"
                          (click)="confirm.set(row)"
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
            [heading]="programs().length ? 'No classes here' : 'Add a program first'"
            [description]="
              programs().length
                ? 'A class belongs to one program and holds the students who study together.'
                : 'Classes live inside a program, so there is nothing to put one in yet.'
            "
          >
            @if (canCreate() && programs().length) {
              <button appButton variant="primary" type="button" (click)="startCreate()">
                New class
              </button>
            }
          </app-empty>
        }
      </div>
    </div>

    <app-modal
      [open]="editing() !== null"
      [heading]="editing()?.id ? 'Edit class' : 'New class'"
      hasActions
      (closed)="editing.set(null)"
    >
      <form class="space-y-4" [formGroup]="form" (ngSubmit)="save()">
        <app-field label="Program" for="class-program">
          <select id="class-program" [class]="select" formControlName="program_id">
            @for (program of programs(); track program.id) {
              <option [value]="program.id">{{ program.code }} · {{ program.name }}</option>
            }
          </select>
        </app-field>
        <app-field label="Name" for="class-name" hint="Unique within its program.">
          <input id="class-name" [class]="input" formControlName="name" placeholder="1st Year" />
        </app-field>
        @if (formError()) {
          <p class="text-[13px] text-danger" role="alert">{{ formError() }}</p>
        }
      </form>

      <button appButton variant="secondary" modal-actions type="button" (click)="editing.set(null)">
        Cancel
      </button>
      <button
        appButton
        variant="primary"
        modal-actions
        type="button"
        [disabled]="form.invalid"
        [loading]="saving()"
        (click)="save()"
      >
        {{ editing()?.id ? 'Save changes' : 'Create class' }}
      </button>
    </app-modal>

    <app-modal
      [open]="confirm() !== null"
      size="sm"
      heading="Delete this class?"
      [description]="confirm() ? confirm()!.program_code + ' · ' + confirm()!.name : ''"
      hasActions
      (closed)="confirm.set(null)"
    >
      <p class="measure">
        A class with enrolled students or attendance registers cannot be deleted.
      </p>
      @if (deleteError()) {
        <p class="mt-3 text-[13px] text-danger" role="alert">{{ deleteError() }}</p>
      }

      <button appButton variant="secondary" modal-actions type="button" (click)="confirm.set(null)">
        Keep class
      </button>
      <button
        appButton
        variant="danger"
        modal-actions
        type="button"
        [loading]="deleting()"
        (click)="remove()"
      >
        Delete class
      </button>
    </app-modal>
  `,
})
export class Classes {
  private readonly api = inject(ClassesApi);
  private readonly programsApi = inject(ProgramsApi);
  private readonly tokens = inject(TokenService);

  protected readonly input = INPUT;
  protected readonly select = SELECT;
  protected readonly table = TABLE;
  protected readonly tableWrap = TABLE_WRAP;
  protected readonly th = TH;
  protected readonly td = TD;

  protected readonly list = new ListState<ClassRow>();
  protected readonly programs = signal<Program[]>([]);
  protected readonly canCreate = computed(() => this.tokens.has(Permission.ClassesCreate));
  protected readonly canUpdate = computed(() => this.tokens.has(Permission.ClassesUpdate));
  protected readonly canDelete = computed(() => this.tokens.has(Permission.ClassesDelete));
  /** The actions column is only worth a column if either action is available. */
  protected readonly canAct = computed(() => this.canUpdate() || this.canDelete());

  protected readonly editing = signal<Partial<ClassRow> | null>(null);
  protected readonly confirm = signal<ClassRow | null>(null);
  protected readonly saving = signal(false);
  protected readonly deleting = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly deleteError = signal<string | null>(null);

  private query = '';
  private programId = '';

  protected readonly form = inject(FormBuilder).nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    program_id: ['', Validators.required],
  });

  protected readonly reload = (): void => {
    this.list.load(({ limit, offset }) =>
      this.api.list({ limit, offset, q: this.query, program_id: this.programId }),
    );
  };

  private readonly runSearch = debounced<string>(250, (value) => {
    this.query = value;
    this.list.reset();
    this.reload();
  });

  constructor() {
    // Every program, for the filter and the form: the list is small and both
    // controls are useless without all of it.
    this.programsApi.list({ limit: 100 }).subscribe({
      next: (page) => this.programs.set(page.items),
      error: () => this.programs.set([]),
    });
    this.reload();
  }

  protected search(value: string): void {
    this.runSearch(value);
  }

  protected filterProgram(value: string): void {
    this.programId = value;
    this.list.reset();
    this.reload();
  }

  protected startCreate(): void {
    this.form.reset({ name: '', program_id: this.programId || this.programs()[0]?.id || '' });
    this.formError.set(null);
    this.editing.set({});
  }

  protected startEdit(row: ClassRow): void {
    this.form.reset({ name: row.name, program_id: row.program_id });
    this.formError.set(null);
    this.editing.set(row);
  }

  protected save(): void {
    if (this.form.invalid || this.saving()) {
      return;
    }
    const current = this.editing();
    const body = this.form.getRawValue();
    this.saving.set(true);
    this.formError.set(null);

    const request = current?.id ? this.api.update(current.id, body) : this.api.create(body);
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.editing.set(null);
        this.reload();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.formError.set(apiErrorMessage(err, 'Could not save this class.'));
      },
    });
  }

  protected remove(): void {
    const row = this.confirm();
    if (!row || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.deleteError.set(null);

    this.api.remove(row.id).subscribe({
      next: () => {
        this.deleting.set(false);
        this.confirm.set(null);
        this.list.offset.set(this.list.offsetAfterDelete());
        this.reload();
      },
      error: (err: unknown) => {
        this.deleting.set(false);
        this.deleteError.set(apiErrorMessage(err, 'Could not delete this class.'));
      },
    });
  }
}
