import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { apiErrorMessage } from '../../core/api-error';
import { ClassRow, Faculty, Subject } from '../../core/api/domain';
import { ClassesApi, FacultyApi, SubjectsApi } from '../../core/api/services';
import { Permission } from '../../core/auth/permissions';
import { TokenService } from '../../core/auth/token.service';
import { ListState, debounced } from '../../shared/list-state';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT, SELECT, TABLE, TABLE_WRAP, TD, TD_NUM, TH, TH_NUM } from '../../shared/ui/controls';
import { Empty } from '../../shared/ui/empty';
import { Field } from '../../shared/ui/field';
import { Modal } from '../../shared/ui/modal';
import { PageHeader } from '../../shared/ui/page-header';
import { Pagination } from '../../shared/ui/pagination';

/**
 * Subjects — taught subjects, shared across classes and programs.
 *
 * Seats are the column that matters day to day, so they get a figure and a
 * fill: a subject at 30 of 30 has to be visible without reading the number.
 * Which classes a subject runs in is edited here too, since that set is the
 * subject's own property rather than the class's.
 */
@Component({
  selector: 'app-subjects',
  imports: [ReactiveFormsModule, Badge, Button, Empty, Field, Modal, PageHeader, Pagination],
  template: `
    <div class="space-y-6">
      <app-page-header
        heading="Subjects"
        description="Taught to one or more classes, across programs — Medical and Engineering can share the same English."
      >
        @if (canCreate()) {
          <button appButton variant="primary" type="button" actions (click)="startCreate()">
            New subject
          </button>
        }
      </app-page-header>

      <div class="flex flex-wrap items-center gap-3">
        <select
          [class]="select"
          class="max-w-[15rem]"
          aria-label="Filter by class"
          (change)="filterClass($any($event.target).value)"
        >
          <option value="">All classes</option>
          @for (row of classes(); track row.id) {
            <option [value]="row.id">{{ row.program_code }} · {{ row.name }}</option>
          }
        </select>
        <input
          type="search"
          [class]="input"
          class="max-w-xs"
          placeholder="Search name or code"
          aria-label="Search subjects"
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
                <th [class]="th" scope="col">Subject</th>
                <th [class]="th + ' hidden md:table-cell'" scope="col">Teacher</th>
                <th [class]="th + ' hidden lg:table-cell'" scope="col">Classes</th>
                <th [class]="thNum" scope="col">Seats</th>
                @if (canAct()) {
                  <th [class]="th" scope="col"><span class="sr-only">Actions</span></th>
                }
              </tr>
            </thead>
            <tbody>
              @for (subject of list.items(); track subject.id) {
                <tr class="hover:bg-sunken">
                  <td [class]="td">
                    <app-badge tone="accent">{{ subject.code }}</app-badge>
                  </td>
                  <td [class]="td">
                    {{ subject.name }}
                    <!-- Kept beside the name where the column itself is gone. -->
                    @if (subject.teacher_name) {
                      <span class="block text-[12.5px] text-ink-muted md:hidden">
                        {{ subject.teacher_name }}
                      </span>
                    }
                  </td>
                  <td [class]="td + ' hidden md:table-cell'">
                    @if (subject.teacher_name) {
                      {{ subject.teacher_name }}
                    } @else {
                      <span class="text-ink-faint">Unassigned</span>
                    }
                  </td>
                  <td [class]="td + ' hidden lg:table-cell'">
                    @if (subject.classes.length) {
                      <span class="text-ink-muted">{{ classNames(subject) }}</span>
                    } @else {
                      <span class="text-ink-faint">Not timetabled</span>
                    }
                  </td>
                  <td [class]="tdNum">
                    <span class="whitespace-nowrap">
                      {{ subject.student_count }}/{{ subject.student_limit }}
                    </span>
                    <!-- A fill, so a full subject is visible before the number
                         is read. Width is a style, not a class: it is data. -->
                    <span class="mt-1 block h-1 w-full rounded-full bg-line">
                      <span
                        class="block h-1 rounded-full"
                        [class]="subject.seats_available ? 'bg-accent' : 'bg-warn'"
                        [style.width.%]="fillPercent(subject)"
                      ></span>
                    </span>
                  </td>
                  @if (canAct()) {
                    <td [class]="td + ' text-right whitespace-nowrap'">
                      @if (canUpdate()) {
                        <button
                          appButton
                          variant="ghost"
                          size="sm"
                          type="button"
                          (click)="startEdit(subject)"
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
                          (click)="confirm.set(subject)"
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
            heading="No subjects yet"
            description="A subject is taught to any number of classes and caps how many students may take it."
          >
            @if (canCreate()) {
              <button appButton variant="primary" type="button" (click)="startCreate()">
                New subject
              </button>
            }
          </app-empty>
        }
      </div>
    </div>

    <app-modal
      [open]="editing() !== null"
      [heading]="editing()?.id ? 'Edit subject' : 'New subject'"
      size="lg"
      hasActions
      (closed)="editing.set(null)"
    >
      <form class="space-y-4" [formGroup]="form" (ngSubmit)="save()">
        <div class="grid gap-4 sm:grid-cols-2">
          <app-field label="Name" for="subject-name">
            <input
              id="subject-name"
              [class]="input"
              formControlName="name"
              placeholder="Mathematics I"
            />
          </app-field>
          <app-field label="Code" for="subject-code" hint="Letters, digits and dashes.">
            <input
              id="subject-code"
              [class]="input"
              formControlName="code"
              placeholder="MATH101"
              maxlength="16"
            />
          </app-field>
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <app-field
            label="Teacher"
            for="subject-teacher"
            hint="Faculty, not sign-in accounts. Can be left for later."
          >
            <select id="subject-teacher" [class]="select" formControlName="teacher_id">
              <option value="">Unassigned</option>
              @for (member of teachers(); track member.id) {
                <option [value]="member.id">
                  {{ member.full_name }}
                  @if (member.designation) {
                    · {{ member.designation }}
                  }
                </option>
              }
            </select>
          </app-field>
        </div>

        <app-field
          label="Student limit"
          for="subject-limit"
          [hint]="limitHint()"
          [error]="limitError()"
        >
          <input
            id="subject-limit"
            type="number"
            min="1"
            [class]="input"
            class="max-w-[8rem]"
            formControlName="student_limit"
          />
        </app-field>

        <fieldset>
          <legend class="text-[13px] font-medium text-ink">Taught to</legend>
          <p class="mt-0.5 text-[12.5px] text-ink-muted">
            Any classes, in any programs. Leave empty to add it to the timetable later.
          </p>
          <div class="mt-2 max-h-52 overflow-y-auto rounded-control border border-line">
            @for (row of classes(); track row.id) {
              <label
                class="flex cursor-pointer items-center gap-3 border-b border-line-soft px-3 py-2
                       text-[14px] last:border-b-0 hover:bg-sunken"
              >
                <input
                  type="checkbox"
                  class="accent-accent"
                  [checked]="chosen().has(row.id)"
                  (change)="toggleClass(row.id)"
                />
                <app-badge tone="neutral">{{ row.program_code }}</app-badge>
                <span>{{ row.name }}</span>
              </label>
            } @empty {
              <p class="px-3 py-4 text-[13.5px] text-ink-muted">No classes exist yet.</p>
            }
          </div>
        </fieldset>

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
        {{ editing()?.id ? 'Save changes' : 'Create subject' }}
      </button>
    </app-modal>

    <app-modal
      [open]="confirm() !== null"
      size="sm"
      heading="Delete this subject?"
      [description]="confirm() ? confirm()!.name + ' (' + confirm()!.code + ')' : ''"
      hasActions
      (closed)="confirm.set(null)"
    >
      <p class="measure">
        A subject students have taken up cannot be deleted — unenroll them first.
      </p>
      @if (deleteError()) {
        <p class="mt-3 text-[13px] text-danger" role="alert">{{ deleteError() }}</p>
      }

      <button appButton variant="secondary" modal-actions type="button" (click)="confirm.set(null)">
        Keep subject
      </button>
      <button
        appButton
        variant="danger"
        modal-actions
        type="button"
        [loading]="deleting()"
        (click)="remove()"
      >
        Delete subject
      </button>
    </app-modal>
  `,
})
export class Subjects {
  private readonly api = inject(SubjectsApi);
  private readonly classesApi = inject(ClassesApi);
  private readonly facultyApi = inject(FacultyApi);
  private readonly tokens = inject(TokenService);

  protected readonly input = INPUT;
  protected readonly select = SELECT;
  protected readonly table = TABLE;
  protected readonly tableWrap = TABLE_WRAP;
  protected readonly th = TH;
  protected readonly thNum = TH_NUM;
  protected readonly td = TD;
  protected readonly tdNum = TD_NUM;

  protected readonly list = new ListState<Subject>();
  protected readonly classes = signal<ClassRow[]>([]);
  protected readonly teachers = signal<Faculty[]>([]);
  protected readonly canCreate = computed(() => this.tokens.has(Permission.SubjectsCreate));
  protected readonly canUpdate = computed(() => this.tokens.has(Permission.SubjectsUpdate));
  protected readonly canDelete = computed(() => this.tokens.has(Permission.SubjectsDelete));
  /** The actions column is only worth a column if either action is available. */
  protected readonly canAct = computed(() => this.canUpdate() || this.canDelete());

  protected readonly editing = signal<Partial<Subject> | null>(null);
  protected readonly confirm = signal<Subject | null>(null);
  protected readonly chosen = signal<Set<string>>(new Set());
  protected readonly saving = signal(false);
  protected readonly deleting = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly deleteError = signal<string | null>(null);

  private query = '';
  private classId = '';

  protected readonly form = inject(FormBuilder).nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(150)]],
    code: ['', [Validators.required, Validators.pattern(/^[A-Za-z0-9-]{2,16}$/)]],
    student_limit: [30, [Validators.required, Validators.min(1), Validators.max(10000)]],
    teacher_id: [''],
  });

  /** The limit cannot go below the students already enrolled. */
  protected readonly limitHint = computed(() => {
    const current = this.editing();
    return current?.id ? `${current.student_count} student(s) enrolled.` : 'Defaults to 30.';
  });

  protected readonly limitError = computed(() => {
    const current = this.editing();
    const value = this.form.controls.student_limit.value;
    return current?.id && current.student_count !== undefined && value < current.student_count
      ? 'Lower than the students already enrolled.'
      : null;
  });

  protected readonly reload = (): void => {
    this.list.load(({ limit, offset }) =>
      this.api.list({ limit, offset, q: this.query, class_id: this.classId }),
    );
  };

  private readonly runSearch = debounced<string>(250, (value) => {
    this.query = value;
    this.list.reset();
    this.reload();
  });

  constructor() {
    this.classesApi.list({ limit: 100 }).subscribe({
      next: (page) => this.classes.set(page.items),
      error: () => this.classes.set([]),
    });
    // Current staff only: a former colleague should not be assignable, though
    // one already assigned still shows, because the record says so.
    // 100 is the API's maximum page size; asking for more is a 422.
    this.facultyApi.list({ limit: 100, is_active: 'true' }).subscribe({
      next: (page) => this.teachers.set(page.items),
      error: () => this.teachers.set([]),
    });
    this.reload();
  }

  protected search(value: string): void {
    this.runSearch(value);
  }

  protected filterClass(value: string): void {
    this.classId = value;
    this.list.reset();
    this.reload();
  }

  protected classNames(subject: Subject): string {
    return subject.classes.map((row) => row.name).join(', ');
  }

  protected fillPercent(subject: Subject): number {
    return subject.student_limit
      ? Math.min(100, (subject.student_count / subject.student_limit) * 100)
      : 0;
  }

  protected toggleClass(id: string): void {
    const next = new Set(this.chosen());
    if (!next.delete(id)) {
      next.add(id);
    }
    this.chosen.set(next);
  }

  protected startCreate(): void {
    this.form.reset({ name: '', code: '', student_limit: 30, teacher_id: '' });
    this.chosen.set(new Set(this.classId ? [this.classId] : []));
    this.formError.set(null);
    this.editing.set({});
  }

  protected startEdit(subject: Subject): void {
    this.form.reset({
      name: subject.name,
      code: subject.code,
      student_limit: subject.student_limit,
      teacher_id: subject.teacher_id ?? '',
    });
    this.chosen.set(new Set(subject.classes.map((row) => row.id)));
    this.formError.set(null);
    this.editing.set(subject);
  }

  protected save(): void {
    if (this.form.invalid || this.saving()) {
      return;
    }
    const current = this.editing();
    const raw = this.form.getRawValue();
    // '' is the "Unassigned" option; the API wants null to clear the column,
    // and would reject the empty string as a uuid.
    const body = { ...raw, teacher_id: raw.teacher_id || null };
    const classIds = [...this.chosen()];
    this.saving.set(true);
    this.formError.set(null);

    const done = () => {
      this.saving.set(false);
      this.editing.set(null);
      this.reload();
    };
    const failed = (err: unknown) => {
      this.saving.set(false);
      this.formError.set(apiErrorMessage(err, 'Could not save this subject.'));
    };

    if (!current?.id) {
      this.api.create({ ...body, class_ids: classIds }).subscribe({ next: done, error: failed });
      return;
    }

    // Details and the class set are two endpoints: PATCH carries the fields,
    // PUT replaces the collection. Sequenced so a rejected class change does
    // not leave the name saved and the page looking successful.
    const id = current.id;
    this.api.update(id, body).subscribe({
      next: () => this.api.setClasses(id, classIds).subscribe({ next: done, error: failed }),
      error: failed,
    });
  }

  protected remove(): void {
    const subject = this.confirm();
    if (!subject || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.deleteError.set(null);

    this.api.remove(subject.id).subscribe({
      next: () => {
        this.deleting.set(false);
        this.confirm.set(null);
        this.list.offset.set(this.list.offsetAfterDelete());
        this.reload();
      },
      error: (err: unknown) => {
        this.deleting.set(false);
        this.deleteError.set(apiErrorMessage(err, 'Could not delete this subject.'));
      },
    });
  }
}
