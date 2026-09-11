import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api-error';
import { Exam, ExamMarkInput, ExamPaper, MarkSheet } from '../../core/api/domain';
import { ExamsApi } from '../../core/api/services';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT } from '../../shared/ui/controls';
import { Empty } from '../../shared/ui/empty';

/** What the caller has typed for one student, before saving. */
interface Draft {
  obtained: number | null;
  absent: boolean;
}

/**
 * One exam: its papers, and the mark sheet for whichever is open.
 *
 * **Marking is the only place in this app where a permission is not the whole
 * answer.** The API also asks whether you teach the subject, so each paper
 * carries `can_mark` and the sheet renders read-only when you do not — showing
 * a form that will be refused is worse than showing none. A paper you may mark
 * is listed with its subject's teacher beside it, so the reason is legible
 * rather than mysterious.
 *
 * Marks are held locally and saved in one request, like the attendance
 * register: entering a class's results is a run of typing, not forty round
 * trips.
 */
@Component({
  selector: 'app-exam-detail',
  imports: [RouterLink, Badge, Button, Empty],
  template: `
    <div class="space-y-6">
      <div class="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div class="min-w-0">
          <a routerLink="/exams" class="text-[13px] text-ink-muted hover:text-ink">Exams</a>
          <h1 class="mt-0.5 text-[26px] leading-tight">{{ exam()?.title ?? 'Exam' }}</h1>
          @if (exam(); as e) {
            <p class="mt-1 flex flex-wrap items-center gap-2 text-[14px] text-ink-muted">
              <app-badge tone="accent">{{ e.class.program_code }}</app-badge>
              <span>{{ e.class.name }}</span>
              <span>·</span>
              <span>{{ longDate(e.date) }}</span>
              <span>·</span>
              <span>{{ e.scope === 'class' ? 'All subjects' : 'Single subject' }}</span>
            </p>
          }
        </div>
        <a appButton variant="secondary" routerLink="/exams">Done</a>
      </div>

      @if (error(); as message) {
        <p
          class="rounded-panel border border-danger/25 bg-danger-soft px-4 py-3 text-[14px] text-danger"
          role="alert"
        >
          {{ message }}
        </p>
      }

      @if (exam(); as e) {
        <div class="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <!-- Papers -->
          <nav aria-label="Papers">
            <ul
              class="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:gap-1 lg:overflow-visible lg:pb-0"
            >
              @for (paper of e.papers; track paper.id) {
                <li class="flex-none lg:flex-auto">
                  <button type="button" [class]="paperClasses(paper)" (click)="open(paper)">
                    <span class="flex items-center gap-2">
                      <app-badge tone="neutral">{{ paper.subject_code }}</app-badge>
                      <span class="truncate text-[14px]">{{ paper.subject_name }}</span>
                    </span>
                    <span class="mt-0.5 block text-[12.5px] text-ink-muted">
                      {{ paper.teacher_name ?? 'No teacher assigned' }} · {{ paper.marked }} marked
                    </span>
                  </button>
                </li>
              }
            </ul>
          </nav>

          <!-- Mark sheet -->
          @if (sheet(); as s) {
            <section class="rounded-panel border border-line bg-surface">
              <header
                class="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b
                       border-line px-5 py-3.5"
              >
                <div>
                  <h2 class="text-[17px] leading-6">{{ s.paper.subject_name }}</h2>
                  <p class="mt-0.5 text-[13px] text-ink-muted">
                    Out of {{ s.paper.total_marks }} ·
                    {{ s.paper.teacher_name ?? 'no teacher assigned' }}
                  </p>
                </div>
                <div class="flex flex-wrap items-center gap-2">
                  <app-badge tone="ok">{{ tally().entered }} entered</app-badge>
                  @if (tally().absent) {
                    <app-badge tone="warn">{{ tally().absent }} absent</app-badge>
                  }
                  @if (tally().blank) {
                    <app-badge tone="neutral">{{ tally().blank }} blank</app-badge>
                  }
                </div>
              </header>

              @if (!s.can_mark) {
                <p class="border-b border-line bg-sunken px-5 py-2.5 text-[13px] text-ink-muted">
                  Read-only: only
                  {{
                    s.paper.teacher_name
                      ? s.paper.teacher_name + ', who teaches this subject,'
                      : 'the subject teacher'
                  }}
                  can enter these marks.
                </p>
              } @else {
                <div
                  class="flex flex-wrap items-center justify-between gap-3 border-b border-line
                         bg-sunken px-5 py-2.5"
                >
                  <span class="text-[13px] text-ink-muted">
                    Leave a box empty to leave the mark unrecorded.
                  </span>
                  <div class="flex items-center gap-3">
                    @if (dirtyCount()) {
                      <span class="text-[13px] text-ink-muted"> {{ dirtyCount() }} unsaved </span>
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
                @for (mark of s.marks; track mark.student.id) {
                  <li class="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2.5">
                    <span class="w-20 shrink-0 text-[13px] text-ink-muted">
                      {{ mark.student.roll_no }}
                    </span>
                    <span class="min-w-0 flex-1 text-[14.5px]">
                      {{ mark.student.first_name }} {{ mark.student.last_name }}
                    </span>

                    <div class="flex items-center gap-3">
                      <label class="flex items-center gap-2 text-[13px] text-ink-muted">
                        <input
                          type="checkbox"
                          class="accent-accent"
                          [disabled]="!s.can_mark"
                          [checked]="draftFor(mark.student.id).absent"
                          (change)="setAbsent(mark.student.id, $any($event.target).checked)"
                        />
                        Absent
                      </label>
                      <input
                        type="number"
                        min="0"
                        [max]="s.paper.total_marks"
                        [class]="input"
                        class="w-24 text-right"
                        [disabled]="!s.can_mark || draftFor(mark.student.id).absent"
                        [value]="draftFor(mark.student.id).obtained ?? ''"
                        [attr.aria-label]="'Marks for ' + mark.student.roll_no"
                        (input)="setMark(mark.student.id, $any($event.target).value)"
                      />
                      <span class="w-10 text-[13px] text-ink-muted">
                        / {{ s.paper.total_marks }}
                      </span>
                    </div>
                  </li>
                } @empty {
                  <app-empty
                    heading="Nobody sits this paper"
                    description="No student enrolled in this class has taken this subject up."
                  />
                }
              </ul>
            </section>
          } @else if (loading()) {
            <p
              class="rounded-panel border border-line bg-surface px-5 py-10 text-center text-[14px] text-ink-muted"
            >
              Loading…
            </p>
          }
        </div>
      }
    </div>
  `,
})
export class ExamDetail {
  /** Route param, bound by `withComponentInputBinding()`. */
  readonly id = input.required<string>();

  private readonly api = inject(ExamsApi);

  protected readonly input = INPUT;

  protected readonly exam = signal<Exam | null>(null);
  protected readonly sheet = signal<MarkSheet | null>(null);
  protected readonly loading = signal(false);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly saveError = signal<string | null>(null);

  /** Working copy, keyed by student. Saved as a diff against `original`. */
  private readonly drafts = signal<Map<string, Draft>>(new Map());
  private original = new Map<string, Draft>();

  protected readonly tally = computed(() => {
    let entered = 0;
    let absent = 0;
    let blank = 0;
    for (const draft of this.drafts().values()) {
      if (draft.absent) {
        absent += 1;
      } else if (draft.obtained === null) {
        blank += 1;
      } else {
        entered += 1;
      }
    }
    return { entered, absent, blank };
  });

  protected readonly dirtyCount = computed(() => this.changed().length);

  constructor() {
    effect(() => {
      const id = this.id();
      this.api.get(id).subscribe({
        next: (exam) => {
          this.exam.set(exam);
          const first = exam.papers[0];
          if (first) {
            this.open(first);
          }
        },
        error: (err: unknown) => this.error.set(apiErrorMessage(err, 'Could not load this exam.')),
      });
    });
  }

  protected longDate(iso: string): string {
    return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  }

  protected paperClasses(paper: ExamPaper): string {
    const base =
      'w-full min-w-[13rem] rounded-control border px-3 py-2 text-left transition-colors lg:min-w-0';
    return this.sheet()?.paper.id === paper.id
      ? `${base} border-accent-line bg-accent-soft text-ink`
      : `${base} border-line bg-surface text-ink-muted hover:bg-sunken hover:text-ink`;
  }

  protected open(paper: ExamPaper): void {
    this.loading.set(true);
    this.saveError.set(null);
    this.api.marks(paper.id).subscribe({
      next: (sheet) => this.accept(sheet),
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err, 'Could not load this mark sheet.'));
      },
    });
  }

  protected draftFor(studentId: string): Draft {
    return this.drafts().get(studentId) ?? { obtained: null, absent: false };
  }

  protected setMark(studentId: string, raw: string): void {
    const value = raw.trim() === '' ? null : Number(raw);
    this.patch(studentId, {
      obtained: value === null || Number.isNaN(value) ? null : value,
      absent: false,
    });
  }

  protected setAbsent(studentId: string, absent: boolean): void {
    // Absent and a score are mutually exclusive — the database says so too.
    this.patch(studentId, { obtained: absent ? null : this.draftFor(studentId).obtained, absent });
  }

  private patch(studentId: string, draft: Draft): void {
    const next = new Map(this.drafts());
    next.set(studentId, draft);
    this.drafts.set(next);
  }

  protected save(): void {
    const sheet = this.sheet();
    const changes = this.changed();
    if (!sheet || !changes.length || this.saving()) {
      return;
    }
    this.saving.set(true);
    this.saveError.set(null);

    this.api.setMarks(sheet.paper.id, changes).subscribe({
      next: (updated) => {
        this.saving.set(false);
        this.accept(updated);
        // The paper's marked count moved, so the rail is out of date.
        this.api.get(this.id()).subscribe({ next: (exam) => this.exam.set(exam) });
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.saveError.set(apiErrorMessage(err, 'Could not save these marks.'));
      },
    });
  }

  /** Only the students whose entry differs from what is stored. */
  private changed(): ExamMarkInput[] {
    const changes: ExamMarkInput[] = [];
    for (const [studentId, draft] of this.drafts()) {
      const before = this.original.get(studentId);
      if (!before || before.obtained !== draft.obtained || before.absent !== draft.absent) {
        changes.push({
          student_id: studentId,
          obtained: draft.absent ? null : draft.obtained,
          is_absent: draft.absent,
        });
      }
    }
    return changes;
  }

  private accept(sheet: MarkSheet): void {
    this.loading.set(false);
    this.sheet.set(sheet);
    const drafts = new Map<string, Draft>(
      sheet.marks.map((mark) => [
        mark.student.id,
        { obtained: mark.obtained, absent: mark.is_absent },
      ]),
    );
    this.drafts.set(drafts);
    this.original = new Map([...drafts].map(([id, draft]) => [id, { ...draft }]));
  }
}
