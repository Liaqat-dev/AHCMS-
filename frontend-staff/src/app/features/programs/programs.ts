import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { apiErrorMessage } from '../../core/api-error';
import { ProgramsApi } from '../../core/api/services';
import { Program } from '../../core/api/domain';
import { Permission } from '../../core/auth/permissions';
import { TokenService } from '../../core/auth/token.service';
import { ListState, debounced } from '../../shared/list-state';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT, TABLE, TABLE_WRAP, TD, TH } from '../../shared/ui/controls';
import { Empty } from '../../shared/ui/empty';
import { Field } from '../../shared/ui/field';
import { Modal } from '../../shared/ui/modal';
import { PageHeader } from '../../shared/ui/page-header';
import { Pagination } from '../../shared/ui/pagination';

/**
 * Programs — the courses of study students are admitted to.
 *
 * The three-letter code is the identifier people actually quote, so it leads
 * the row and is set in the accent, the way a stamped reference would be.
 */
@Component({
  selector: 'app-programs',
  imports: [ReactiveFormsModule, Badge, Button, Empty, Field, Modal, PageHeader, Pagination],
  template: `
    <div class="space-y-6">
      <app-page-header
        heading="Programs"
        description="A course of study, identified by a three-letter code that classes and reports quote."
      >
        @if (canCreate()) {
          <button appButton variant="primary" type="button" actions (click)="startCreate()">
            New program
          </button>
        }
      </app-page-header>

      <div class="flex flex-wrap items-center gap-3">
        <input
          type="search"
          [class]="input"
          class="max-w-xs"
          placeholder="Search name or code"
          aria-label="Search programs"
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
                <th [class]="th" scope="col">Code</th>
                <th [class]="th" scope="col">Name</th>
                <th [class]="th" scope="col">Created by</th>
                @if (canAct()) {
                  <th [class]="th" scope="col"><span class="sr-only">Actions</span></th>
                }
              </tr>
            </thead>
            <tbody>
              @for (program of list.items(); track program.id) {
                <tr class="hover:bg-sunken">
                  <td [class]="td">
                    <app-badge tone="accent">{{ program.code }}</app-badge>
                  </td>
                  <td [class]="td">{{ program.name }}</td>
                  <td [class]="td + ' text-ink-muted'">{{ program.created_by_name ?? '—' }}</td>
                  @if (canAct()) {
                    <td [class]="td + ' text-right whitespace-nowrap'">
                      @if (canUpdate()) {
                        <button
                          appButton
                          variant="ghost"
                          size="sm"
                          type="button"
                          (click)="startEdit(program)"
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
                          (click)="confirm.set(program)"
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
            heading="No programs yet"
            description="A program is the top of the structure: classes belong to one, and subjects are taught across them."
          >
            @if (canCreate()) {
              <button appButton variant="primary" type="button" (click)="startCreate()">
                New program
              </button>
            }
          </app-empty>
        }
      </div>
    </div>

    <!-- Create / edit -->
    <app-modal
      [open]="editing() !== null"
      [heading]="editing()?.id ? 'Edit program' : 'New program'"
      hasActions
      (closed)="editing.set(null)"
    >
      <form class="space-y-4" [formGroup]="form" (ngSubmit)="save()">
        <app-field label="Name" for="program-name">
          <input
            id="program-name"
            [class]="input"
            formControlName="name"
            placeholder="Engineering"
          />
        </app-field>
        <app-field
          label="Code"
          for="program-code"
          hint="Exactly three letters. Stored in capitals."
          [error]="codeError()"
        >
          <input
            id="program-code"
            [class]="input"
            formControlName="code"
            maxlength="3"
            placeholder="ENG"
            autocapitalize="characters"
          />
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
        {{ editing()?.id ? 'Save changes' : 'Create program' }}
      </button>
    </app-modal>

    <!-- Delete -->
    <app-modal
      [open]="confirm() !== null"
      size="sm"
      heading="Delete this program?"
      [description]="confirm() ? confirm()!.name + ' (' + confirm()!.code + ')' : ''"
      hasActions
      (closed)="confirm.set(null)"
    >
      <p class="measure">
        A program with classes cannot be deleted — move or delete its classes first.
      </p>
      @if (deleteError()) {
        <p class="mt-3 text-[13px] text-danger" role="alert">{{ deleteError() }}</p>
      }

      <button appButton variant="secondary" modal-actions type="button" (click)="confirm.set(null)">
        Keep program
      </button>
      <button
        appButton
        variant="danger"
        modal-actions
        type="button"
        [loading]="deleting()"
        (click)="remove()"
      >
        Delete program
      </button>
    </app-modal>
  `,
})
export class Programs {
  private readonly api = inject(ProgramsApi);
  private readonly tokens = inject(TokenService);

  protected readonly input = INPUT;
  protected readonly table = TABLE;
  protected readonly tableWrap = TABLE_WRAP;
  protected readonly th = TH;
  protected readonly td = TD;

  protected readonly list = new ListState<Program>();
  protected readonly canCreate = computed(() => this.tokens.has(Permission.ProgramsCreate));
  protected readonly canUpdate = computed(() => this.tokens.has(Permission.ProgramsUpdate));
  protected readonly canDelete = computed(() => this.tokens.has(Permission.ProgramsDelete));
  /** The actions column is only worth a column if either action is available. */
  protected readonly canAct = computed(() => this.canUpdate() || this.canDelete());

  /** `null` closed; a row to edit; `{}` for a new one. */
  protected readonly editing = signal<Partial<Program> | null>(null);
  protected readonly confirm = signal<Program | null>(null);
  protected readonly saving = signal(false);
  protected readonly deleting = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly deleteError = signal<string | null>(null);

  private query = '';

  protected readonly form = inject(FormBuilder).nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    code: ['', [Validators.required, Validators.pattern(/^[A-Za-z]{3}$/)]],
  });

  /** Only speak up once they have typed something wrong, not on an empty field. */
  protected readonly codeError = computed(() => {
    const control = this.form.controls.code;
    return control.value && control.invalid ? 'Three letters, for example ENG.' : null;
  });

  protected readonly reload = (): void => {
    this.list.load(({ limit, offset }) => this.api.list({ limit, offset, q: this.query }));
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

  protected startCreate(): void {
    this.form.reset({ name: '', code: '' });
    this.formError.set(null);
    this.editing.set({});
  }

  protected startEdit(program: Program): void {
    this.form.reset({ name: program.name, code: program.code });
    this.formError.set(null);
    this.editing.set(program);
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
        this.formError.set(apiErrorMessage(err, 'Could not save this program.'));
      },
    });
  }

  protected remove(): void {
    const program = this.confirm();
    if (!program || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.deleteError.set(null);

    this.api.remove(program.id).subscribe({
      next: () => {
        this.deleting.set(false);
        this.confirm.set(null);
        this.list.offset.set(this.list.offsetAfterDelete());
        this.reload();
      },
      error: (err: unknown) => {
        this.deleting.set(false);
        this.deleteError.set(apiErrorMessage(err, 'Could not delete this program.'));
      },
    });
  }
}
