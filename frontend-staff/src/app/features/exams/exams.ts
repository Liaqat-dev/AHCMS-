import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api-error';
import { ClassRow, Exam, Subject } from '../../core/api/domain';
import { ClassesApi, ExamsApi, SubjectsApi } from '../../core/api/services';
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
 * Exams — papers sat by a class on a date.
 *
 * An exam is either one subject or everything the class runs, and the choice is
 * made once at scheduling: the papers are written down then, because a class's
 * subject list changes and an exam is a record of what was actually set.
 *
 * The list leads with the date, because the exam you want is nearly always the
 * one just sat or the one coming up. Marking progress rides on each row for the
 * same reason — the question after an exam is which papers are still outstanding.
 */
@Component({
  selector: 'app-exams',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    Badge,
    Button,
    Empty,
    Field,
    Modal,
    PageHeader,
    Pagination,
  ],
  template: `
    <div class="space-y-6">
      <app-page-header
        heading="Exams"
        description="A paper sat by a class on a date — one subject, or everything the class runs."
      >
        @if (canCreate()) {
          <button
            appButton
            variant="primary"
            type="button"
            actions
            [disabled]="!classes().length"
            (click)="startCreate()"
          >
            Schedule exam
          </button>
        }
      </app-page-header>

      <div class="flex flex-wrap items-center gap-3">
        <select
          [class]="select"
          class="max-w-[14rem]"
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
          placeholder="Search title"
          aria-label="Search exams"
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
                <th [class]="th" scope="col">Date</th>
                <th [class]="th" scope="col">Exam</th>
                <th [class]="th + ' hidden sm:table-cell'" scope="col">Class</th>
                <th [class]="th + ' hidden md:table-cell'" scope="col">Papers</th>
                <th [class]="th" scope="col"><span class="sr-only">Open</span></th>
              </tr>
            </thead>
            <tbody>
              @for (exam of list.items(); track exam.id) {
                <tr class="hover:bg-sunken">
                  <td [class]="td + ' whitespace-nowrap'">
                    {{ exam.date }}
                    @if (isUpcoming(exam)) {
                      <span class="ml-2 text-[12px] text-accent">upcoming</span>
                    }
                  </td>
                  <td [class]="td">
                    {{ exam.title }}
                    <span class="block text-[12.5px] text-ink-muted sm:hidden">
                      {{ exam.class.program_code }} · {{ exam.class.name }}
                    </span>
                  </td>
                  <td [class]="td + ' hidden sm:table-cell'">
                    <app-badge tone="accent">{{ exam.class.program_code }}</app-badge>
                    <span class="ml-2">{{ exam.class.name }}</span>
                  </td>
                  <td [class]="td + ' hidden md:table-cell'">
                    <span class="text-ink-muted">{{ papersLabel(exam) }}</span>
                  </td>
                  <td [class]="td + ' text-right whitespace-nowrap'">
                    <a appButton variant="ghost" size="sm" [routerLink]="['/exams', exam.id]">
                      Open
                    </a>
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
            [heading]="classes().length ? 'No exams yet' : 'Add a class first'"
            [description]="
              classes().length
                ? 'Schedule one over a single subject, or over every subject a class runs.'
                : 'An exam belongs to a class, and none exists yet.'
            "
          >
            @if (canCreate() && classes().length) {
              <button appButton variant="primary" type="button" (click)="startCreate()">
                Schedule exam
              </button>
            }
          </app-empty>
        }
      </div>
    </div>

    <app-modal
      [open]="creating()"
      heading="Schedule an exam"
      description="Its papers are fixed once scheduled, so the class and scope cannot be changed afterwards."
      hasActions
      (closed)="creating.set(false)"
    >
      <form class="space-y-4" [formGroup]="form" (ngSubmit)="save()">
        <app-field label="Title" for="exam-title">
          <input id="exam-title" [class]="input" formControlName="title" placeholder="Mid-term" />
        </app-field>

        <div class="grid gap-4 sm:grid-cols-2">
          <app-field label="Class" for="exam-class">
            <select
              id="exam-class"
              [class]="select"
              formControlName="class_id"
              (change)="loadSubjects($any($event.target).value)"
            >
              @for (row of classes(); track row.id) {
                <option [value]="row.id">{{ row.program_code }} · {{ row.name }}</option>
              }
            </select>
          </app-field>
          <app-field label="Date" for="exam-date" hint="May be in the future.">
            <input id="exam-date" type="date" [class]="input" formControlName="date" />
          </app-field>
        </div>

        <app-field label="Covers" for="exam-scope">
          <select id="exam-scope" [class]="select" formControlName="scope">
            <option value="class">Every subject this class runs</option>
            <option value="subject">A single subject</option>
          </select>
        </app-field>

        @if (form.controls.scope.value === 'subject') {
          <app-field label="Subject" for="exam-subject">
            <select id="exam-subject" [class]="select" formControlName="subject_id">
              <option value="">Choose a subject</option>
              @for (subject of classSubjects(); track subject.id) {
                <option [value]="subject.id">{{ subject.code }} · {{ subject.name }}</option>
              }
            </select>
          </app-field>
        } @else {
          <p class="text-[13px] text-ink-muted">
            {{ classSubjects().length }} paper(s) will be created — one per subject the class runs
            today.
          </p>
        }

        <app-field
          label="Total marks"
          for="exam-total"
          hint="Applied to every paper; adjust individual ones afterwards."
        >
          <input
            id="exam-total"
            type="number"
            min="1"
            [class]="input"
            class="max-w-[8rem]"
            formControlName="total_marks"
          />
        </app-field>

        @if (formError()) {
          <p class="text-[13px] text-danger" role="alert">{{ formError() }}</p>
        }
      </form>

      <button
        appButton
        variant="secondary"
        modal-actions
        type="button"
        (click)="creating.set(false)"
      >
        Cancel
      </button>
      <button
        appButton
        variant="primary"
        modal-actions
        type="button"
        [disabled]="form.invalid || !canSubmit()"
        [loading]="saving()"
        (click)="save()"
      >
        Schedule exam
      </button>
    </app-modal>
  `,
})
export class Exams {
  private readonly api = inject(ExamsApi);
  private readonly classesApi = inject(ClassesApi);
  private readonly subjectsApi = inject(SubjectsApi);
  private readonly tokens = inject(TokenService);

  protected readonly input = INPUT;
  protected readonly select = SELECT;
  protected readonly table = TABLE;
  protected readonly tableWrap = TABLE_WRAP;
  protected readonly th = TH;
  protected readonly td = TD;

  protected readonly list = new ListState<Exam>();
  protected readonly classes = signal<ClassRow[]>([]);
  protected readonly classSubjects = signal<Subject[]>([]);
  protected readonly canCreate = computed(() => this.tokens.has(Permission.ExamsCreate));

  protected readonly creating = signal(false);
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);

  private query = '';
  private classId = '';

  protected readonly form = inject(FormBuilder).nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(150)]],
    class_id: ['', Validators.required],
    date: ['', Validators.required],
    scope: ['class'],
    subject_id: [''],
    total_marks: [100, [Validators.required, Validators.min(1), Validators.max(1000)]],
  });

  /** A single-subject exam needs a subject; a class-wide one needs the class to run some. */
  protected readonly canSubmit = computed(() => {
    const scope = this.form.controls.scope.value;
    return scope === 'subject'
      ? !!this.form.controls.subject_id.value
      : this.classSubjects().length > 0;
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

  protected isUpcoming(exam: Exam): boolean {
    return exam.date > new Date().toISOString().slice(0, 10);
  }

  protected papersLabel(exam: Exam): string {
    const marked = exam.papers.filter((p) => p.marked > 0).length;
    return `${exam.papers.length} paper(s), ${marked} started`;
  }

  protected loadSubjects(classId: string): void {
    this.classSubjects.set([]);
    if (!classId) {
      return;
    }
    this.subjectsApi.list({ class_id: classId, limit: 100 }).subscribe({
      next: (page) => this.classSubjects.set(page.items),
      error: () => this.classSubjects.set([]),
    });
  }

  protected startCreate(): void {
    const first = this.classId || this.classes()[0]?.id || '';
    this.form.reset({
      title: '',
      class_id: first,
      date: new Date().toISOString().slice(0, 10),
      scope: 'class',
      subject_id: '',
      total_marks: 100,
    });
    this.formError.set(null);
    this.loadSubjects(first);
    this.creating.set(true);
  }

  protected save(): void {
    if (this.form.invalid || !this.canSubmit() || this.saving()) {
      return;
    }
    const raw = this.form.getRawValue();
    this.saving.set(true);
    this.formError.set(null);

    this.api
      .create({
        class_id: raw.class_id,
        title: raw.title,
        date: raw.date,
        scope: raw.scope as 'class' | 'subject',
        subject_id: raw.scope === 'subject' ? raw.subject_id : null,
        total_marks: raw.total_marks,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.creating.set(false);
          this.list.reset();
          this.reload();
        },
        error: (err: unknown) => {
          this.saving.set(false);
          this.formError.set(apiErrorMessage(err, 'Could not schedule this exam.'));
        },
      });
  }
}
