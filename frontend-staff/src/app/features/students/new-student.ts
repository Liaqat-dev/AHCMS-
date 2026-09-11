import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Observable, of, switchMap, tap } from 'rxjs';

import { apiErrorMessage } from '../../core/api-error';
import {
  ClassRow,
  Enrollment,
  SessionRow,
  Student,
  StudentCreate,
  StudentUpdate,
  Subject,
} from '../../core/api/domain';
import {
  ClassesApi,
  EnrollmentsApi,
  SessionsApi,
  StudentsApi,
  SubjectsApi,
} from '../../core/api/services';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT, SELECT } from '../../shared/ui/controls';
import { Field } from '../../shared/ui/field';
import { Modal } from '../../shared/ui/modal';

type StepKey = 'personal' | 'education' | 'enrollment' | 'security' | 'fees';

interface StepDef {
  n: number;
  key: StepKey;
  label: string;
  blurb: string;
}

const STEPS: StepDef[] = [
  { n: 1, key: 'personal', label: 'Personal info', blurb: 'Student, guardians, address' },
  { n: 2, key: 'education', label: 'Education', blurb: 'Previous school and SSC' },
  { n: 3, key: 'enrollment', label: 'Enrollment', blurb: 'Intake, class, subjects' },
  { n: 4, key: 'security', label: 'Security', blurb: 'Portal sign-in' },
  { n: 5, key: 'fees', label: 'Fees', blurb: 'Charges and dues' },
];

/** The federating units, as a domicile certificate names them. */
const PROVINCES = [
  'Punjab',
  'Sindh',
  'Khyber Pakhtunkhwa',
  'Balochistan',
  'Gilgit-Baltistan',
  'Azad Jammu & Kashmir',
  'Islamabad Capital Territory',
];

/** Every intake the office admits into: this year's, and the two before it. */
const INTAKES_OFFERED = 3;

/**
 * One choosable intake.
 *
 * A batch runs two years, so 2026 is the "2026-2028" intake. `session` is the
 * row that already exists for that year, or null — a year nobody has admitted
 * into yet has no row, and one is opened when the first student needs it.
 */
interface IntakeOption {
  start_year: number;
  label: string;
  session: SessionRow | null;
}

interface FeeLine {
  description: string;
  amount: number;
}

/**
 * Admission — opening a student's file.
 *
 * Numbered steps, because an admission genuinely is a sequence rather than a
 * set of tabs: nothing can be enrolled and no password issued before the
 * record exists. The rail is also the file's status — a step shows a tick once
 * what it collects has been written.
 *
 * **The intake is the hinge.** It lives on Enrollment rather than with the
 * personal details, because it is not a fact about the person: it is which
 * batch the college is admitting them into, it decides their roll number, and
 * it is what opens the file. Steps 1-2 are held on the page until it is
 * chosen, then written in one call. After that the intake is fixed — the year
 * is inside the roll number — so it renders as text, not a control.
 *
 * Everything after saves on its own, so the form can be abandoned without
 * losing the admission. Fees is interface only and says so; there is no
 * attachments endpoint and no attachments step.
 */
@Component({
  selector: 'app-new-student',
  imports: [ReactiveFormsModule, RouterLink, Badge, Button, Field, Modal],
  template: `
    <div class="space-y-6">
      <!-- Where you are, and what has been committed so far -->
      <div class="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div class="min-w-0">
          <a routerLink="/students" class="text-[13px] text-ink-muted hover:text-ink">Students</a>
          <h1 class="mt-0.5 text-[26px] leading-tight">
            {{ student() ? student()!.full_name : 'New student' }}
          </h1>
          @if (student(); as saved) {
            <p class="mt-1 flex flex-wrap items-center gap-2 text-[14px] text-ink-muted">
              <app-badge tone="accent">{{ saved.roll_no }}</app-badge>
              <span>{{ saved.session.label }}</span>
              @if (saved.missing_fields.length) {
                <app-badge tone="warn">{{ saved.missing_fields.length }} outstanding</app-badge>
              }
            </p>
          } @else {
            <p class="measure mt-1 text-[14px] text-ink-muted">
              A name and an intake open the file and allocate a roll number. Fill in what you have;
              the rest can follow.
            </p>
          }
        </div>
        <a appButton variant="secondary" routerLink="/students">
          {{ student() ? 'Done' : 'Cancel' }}
        </a>
      </div>

      <div class="grid gap-5 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-6">
        <nav aria-label="Admission steps">
          <!--
            Narrow: markers only, joined by the rule that makes them a
            sequence, with the step you are on named underneath. Five of these
            fit a 320px screen, so nothing scrolls sideways and no label is
            truncated to make room.
          -->
          <ol class="flex items-center lg:hidden">
            @for (s of steps; track s.n) {
              <li class="contents">
                <button
                  type="button"
                  [disabled]="!reachable(s)"
                  [class]="dotClasses(s)"
                  [attr.aria-current]="step() === s.n ? 'step' : null"
                  (click)="goTo(s.n)"
                >
                  <span class="sr-only">{{ s.label }}</span>
                  @if (committed(s)) {
                    ✓
                  } @else {
                    {{ s.n }}
                  }
                </button>
                @if (!$last) {
                  <span class="h-px flex-1 bg-line" aria-hidden="true"></span>
                }
              </li>
            }
          </ol>
          <p class="mt-2.5 flex flex-wrap items-baseline gap-x-2 lg:hidden">
            <span class="text-[15px] text-ink">{{ current().label }}</span>
            <span class="text-[12.5px] text-ink-muted">{{ current().blurb }}</span>
          </p>

          <!-- Wide: the full rail, where there is room for it -->
          <ol class="hidden lg:flex lg:flex-col lg:gap-0.5">
            @for (s of steps; track s.n) {
              <li>
                <button
                  type="button"
                  [disabled]="!reachable(s)"
                  [class]="stepClasses(s)"
                  [attr.aria-current]="step() === s.n ? 'step' : null"
                  (click)="goTo(s.n)"
                >
                  <span [class]="markerClasses(s)">
                    @if (committed(s)) {
                      ✓
                    } @else {
                      {{ s.n }}
                    }
                  </span>
                  <span class="min-w-0">
                    <span class="block truncate text-[14px]">{{ s.label }}</span>
                    <span class="block truncate text-[12.5px] text-ink-muted">{{ s.blurb }}</span>
                  </span>
                </button>
              </li>
            }
          </ol>
          @if (!student()) {
            <p class="mt-3 hidden text-[12.5px] text-ink-faint lg:block">
              Choosing an intake on Enrollment opens the file. Sign-in and fees follow from there.
            </p>
          }
        </nav>

        <!-- Panel -->
        <div class="rounded-panel border border-line bg-surface">
          <!-- 1. Personal info -------------------------------------------- -->
          @if (step() === 1) {
            <form class="space-y-5 p-4 sm:p-5" [formGroup]="record" (ngSubmit)="saveRecord(2)">
              <div class="grid gap-4 sm:grid-cols-2">
                <app-field label="First name" for="first-name">
                  <input id="first-name" [class]="input" formControlName="first_name" />
                </app-field>
                <app-field label="Last name" for="last-name">
                  <input id="last-name" [class]="input" formControlName="last_name" />
                </app-field>
                <app-field label="B-Form / CNIC" for="cnic" hint="13 digits; dashes optional.">
                  <input
                    id="cnic"
                    [class]="input"
                    formControlName="b_form_cnic"
                    placeholder="42101-1234567-1"
                  />
                </app-field>
                <app-field label="Date of birth" for="dob">
                  <input id="dob" type="date" [class]="input" formControlName="date_of_birth" />
                </app-field>
                <app-field label="Student's cell number" for="cell">
                  <input
                    id="cell"
                    type="tel"
                    [class]="input"
                    formControlName="cell_no"
                    placeholder="0300 1234567"
                  />
                </app-field>
                <app-field
                  label="Email"
                  for="email"
                  hint="For reaching the student. Signing in uses the roll number."
                >
                  <input id="email" type="email" [class]="input" formControlName="email" />
                </app-field>
              </div>

              <hr class="border-line" />

              <div class="space-y-4">
                <h2 class="text-[15px] text-ink">Guardians</h2>
                <div class="grid gap-4 sm:grid-cols-2">
                  <app-field label="Father's name" for="father">
                    <input id="father" [class]="input" formControlName="father_name" />
                  </app-field>
                  <app-field
                    label="Father's CNIC"
                    for="father-cnic"
                    hint="Siblings share this; it is not checked for uniqueness."
                  >
                    <input
                      id="father-cnic"
                      [class]="input"
                      formControlName="father_cnic"
                      placeholder="42101-1234567-1"
                    />
                  </app-field>
                  <app-field label="Mother's name" for="mother">
                    <input id="mother" [class]="input" formControlName="mother_name" />
                  </app-field>
                  <app-field
                    label="Guardian's cell number"
                    for="guardian-cell"
                    hint="The number the college rings about an absence."
                  >
                    <input
                      id="guardian-cell"
                      type="tel"
                      [class]="input"
                      formControlName="guardian_cell_no"
                      placeholder="0300 1234567"
                    />
                  </app-field>
                </div>
              </div>

              <hr class="border-line" />

              <div class="space-y-4">
                <h2 class="text-[15px] text-ink">Address</h2>
                <app-field label="Postal address" for="address">
                  <textarea
                    id="address"
                    rows="2"
                    [class]="input"
                    formControlName="address"
                  ></textarea>
                </app-field>
                <div class="grid gap-4 sm:grid-cols-2">
                  <app-field label="Province" for="province">
                    <select id="province" [class]="select" formControlName="province">
                      <option value="">Not recorded</option>
                      @for (name of provinces; track name) {
                        <option [value]="name">{{ name }}</option>
                      }
                    </select>
                  </app-field>
                  <app-field
                    label="Domicile district"
                    for="domicile"
                    hint="As written on the domicile certificate, not where they live now."
                  >
                    <input
                      id="domicile"
                      [class]="input"
                      formControlName="domicile_district"
                      placeholder="Rawalpindi"
                    />
                  </app-field>
                </div>
              </div>

              @if (error()) {
                <p class="text-[13px] text-danger" role="alert">{{ error() }}</p>
              }

              <div class="flex flex-wrap items-center justify-end gap-3 border-t border-line pt-4">
                @if (justSaved()) {
                  <p class="text-[13px] text-ok">Saved.</p>
                }
                <button
                  appButton
                  variant="primary"
                  type="submit"
                  [disabled]="namesMissing()"
                  [loading]="saving()"
                >
                  {{ student() ? 'Save changes' : 'Continue' }}
                </button>
              </div>
            </form>
          }

          <!-- 2. Education ------------------------------------------------ -->
          @if (step() === 2) {
            <form class="space-y-5 p-4 sm:p-5" [formGroup]="record" (ngSubmit)="saveRecord(3)">
              <app-field label="Previous school" for="school">
                <input id="school" [class]="input" formControlName="last_school_name" />
              </app-field>

              <div class="grid gap-4 sm:grid-cols-2">
                <app-field label="SSC roll number" for="ssc-roll">
                  <input id="ssc-roll" [class]="input" formControlName="ssc_roll_no" />
                </app-field>
                <app-field label="Year passed" for="ssc-year">
                  <input
                    id="ssc-year"
                    type="number"
                    [class]="input"
                    formControlName="ssc_year"
                    [placeholder]="thisYear"
                  />
                </app-field>
                <app-field label="Marks obtained" for="ssc-got">
                  <input
                    id="ssc-got"
                    type="number"
                    min="0"
                    [class]="input"
                    formControlName="ssc_marks_obtained"
                  />
                </app-field>
                <app-field
                  label="Out of"
                  for="ssc-total"
                  [hint]="sscPercentage() ? sscPercentage() + '%' : 'Boards differ on the total.'"
                >
                  <input
                    id="ssc-total"
                    type="number"
                    min="1"
                    [class]="input"
                    formControlName="ssc_marks_total"
                  />
                </app-field>
              </div>

              @if (error()) {
                <p class="text-[13px] text-danger" role="alert">{{ error() }}</p>
              }

              <div
                class="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4"
              >
                <button appButton variant="secondary" type="button" (click)="goTo(1)">Back</button>
                <div class="flex items-center gap-3">
                  @if (justSaved()) {
                    <p class="text-[13px] text-ok">Saved.</p>
                  }
                  <button appButton variant="primary" type="submit" [loading]="saving()">
                    {{ student() ? 'Save changes' : 'Continue' }}
                  </button>
                </div>
              </div>
            </form>
          }

          <!-- 3. Enrollment ----------------------------------------------- -->
          @if (step() === 3) {
            <div class="space-y-5 p-4 sm:p-5">
              @if (student(); as file) {
                <!-- Fixed: the intake year is inside the roll number -->
                <div class="rounded-control border border-line bg-sunken px-4 py-3">
                  <p class="text-[13px] font-medium text-ink">Intake</p>
                  <p class="mt-1 flex flex-wrap items-center gap-2 text-[14px] text-ink-muted">
                    <span class="text-ink">{{ file.session.label }}</span>
                    <span>·</span>
                    <span>roll number {{ file.roll_no }}</span>
                  </p>
                  <p class="mt-1 text-[12.5px] text-ink-faint">
                    The intake year is part of the roll number, so it cannot be changed once the
                    file is open.
                  </p>
                </div>
              } @else {
                <app-field
                  label="Intake"
                  for="intake"
                  hint="The two-year batch. Roll numbers are allocated from it."
                >
                  <select
                    id="intake"
                    [class]="select"
                    [value]="intakeYear()"
                    (change)="intakeYear.set(+$any($event.target).value)"
                  >
                    @for (intake of intakes(); track intake.start_year) {
                      <option [value]="intake.start_year">{{ intake.label }}</option>
                    }
                  </select>
                </app-field>
              }

              <app-field label="Class" for="enrol-class" hint="Optional now; it can be set later.">
                <select
                  id="enrol-class"
                  [class]="select"
                  [value]="classId()"
                  (change)="chooseClass($any($event.target).value)"
                >
                  <option value="">Not assigned yet</option>
                  @for (row of classes(); track row.id) {
                    <option [value]="row.id">{{ row.program_code }} · {{ row.name }}</option>
                  }
                </select>
              </app-field>

              @if (movingClass()) {
                <p
                  class="rounded-control border border-warn/30 bg-warn-soft px-4 py-3 text-[13.5px] text-warn"
                >
                  Moving class drops every subject picked in the old one, because they belonged to
                  that class. Pick the new class's subjects below.
                </p>
              }

              <fieldset [disabled]="!classId()">
                <legend class="text-[13px] font-medium text-ink">Subjects</legend>
                <p class="mt-0.5 text-[12.5px] text-ink-muted">
                  Optional, and only what this class runs. A full subject cannot be joined.
                </p>
                <div class="mt-2 rounded-control border border-line">
                  @for (subject of classSubjects(); track subject.id) {
                    <label
                      class="flex cursor-pointer items-center gap-3 border-b border-line-soft px-3
                             py-2 text-[14px] last:border-b-0 hover:bg-sunken"
                    >
                      <input
                        type="checkbox"
                        class="accent-accent"
                        [checked]="chosenSubjects().has(subject.id)"
                        [disabled]="!subject.seats_available && !chosenSubjects().has(subject.id)"
                        (change)="toggleSubject(subject.id)"
                      />
                      <app-badge tone="neutral">{{ subject.code }}</app-badge>
                      <span class="flex-1">{{ subject.name }}</span>
                      <span
                        class="text-[12.5px]"
                        [class]="subject.seats_available ? 'text-ink-muted' : 'text-warn'"
                      >
                        {{
                          subject.seats_available ? subject.seats_available + ' seats left' : 'Full'
                        }}
                      </span>
                    </label>
                  } @empty {
                    <p class="px-3 py-4 text-[13.5px] text-ink-muted">
                      {{ classId() ? 'This class runs no subjects yet.' : 'Choose a class first.' }}
                    </p>
                  }
                </div>
              </fieldset>

              @if (error()) {
                <p class="text-[13px] text-danger" role="alert">{{ error() }}</p>
              }

              <div
                class="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4"
              >
                <button appButton variant="secondary" type="button" (click)="goTo(2)">Back</button>
                <div class="flex items-center gap-3">
                  @if (justSaved()) {
                    <p class="text-[13px] text-ok">Saved.</p>
                  }
                  <button
                    appButton
                    variant="primary"
                    type="button"
                    [disabled]="namesMissing()"
                    [loading]="saving()"
                    (click)="saveEnrollment()"
                  >
                    {{ enrolButtonLabel() }}
                  </button>
                </div>
              </div>
            </div>
          }

          <!-- 4. Security ------------------------------------------------- -->
          @if (step() === 4 && student(); as file) {
            <form class="space-y-5 p-4 sm:p-5" [formGroup]="security" (ngSubmit)="savePassword()">
              <div class="rounded-control border border-line bg-sunken px-4 py-3">
                <p class="text-[13px] font-medium text-ink">Signs in as</p>
                <p class="mt-1 text-[17px] tabular-nums text-ink">{{ file.roll_no }}</p>
                <p class="measure mt-1 text-[12.5px] text-ink-faint">
                  Students sign in to the portal with their roll number and this password. Their
                  email address is a contact detail and is never used to sign in.
                </p>
              </div>

              <div class="grid gap-4 sm:grid-cols-2">
                <app-field
                  label="Password"
                  for="pw"
                  hint="Eight characters or more."
                  [error]="
                    security.controls.password.touched && security.controls.password.invalid
                      ? 'Use at least eight characters.'
                      : null
                  "
                >
                  <input
                    id="pw"
                    type="password"
                    autocomplete="new-password"
                    [class]="input"
                    formControlName="password"
                  />
                </app-field>
                <app-field
                  label="Repeat password"
                  for="pw2"
                  [error]="mismatch() ? 'The two passwords are different.' : null"
                >
                  <input
                    id="pw2"
                    type="password"
                    autocomplete="new-password"
                    [class]="input"
                    formControlName="confirm"
                  />
                </app-field>
              </div>

              @if (!file.has_password) {
                <p class="text-[13.5px] text-ink-muted">
                  No password has been issued yet, so this student cannot sign in.
                </p>
              }

              @if (error()) {
                <p class="text-[13px] text-danger" role="alert">{{ error() }}</p>
              }

              <div
                class="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4"
              >
                <button appButton variant="secondary" type="button" (click)="goTo(3)">Back</button>
                <div class="flex items-center gap-3">
                  @if (file.has_password && justSaved()) {
                    <p class="text-[13px] text-ok">Password set.</p>
                  }
                  <button
                    appButton
                    variant="primary"
                    type="submit"
                    [disabled]="security.invalid || mismatch()"
                    [loading]="saving()"
                  >
                    {{ file.has_password ? 'Change password' : 'Set password' }}
                  </button>
                </div>
              </div>
            </form>
          }

          <!-- 5. Fees (interface only) ------------------------------------ -->
          @if (step() === 5) {
            <div class="space-y-5 p-4 sm:p-5">
              <div class="rounded-control border border-warn/30 bg-warn-soft px-4 py-3">
                <p class="text-[13.5px] text-warn">
                  Not stored yet. There is no fees endpoint in the API — this is the shape of the
                  screen, not a working ledger.
                </p>
              </div>

              <ul class="rounded-control border border-line">
                @for (line of fees(); track $index) {
                  <li
                    class="flex flex-wrap items-center gap-2 border-b border-line-soft px-3 py-2
                           last:border-b-0 sm:flex-nowrap sm:gap-3"
                  >
                    <input
                      [class]="input"
                      class="min-w-0 flex-1"
                      placeholder="Admission fee"
                      [value]="line.description"
                      (input)="editFee($index, 'description', $any($event.target).value)"
                    />
                    <input
                      type="number"
                      min="0"
                      [class]="input"
                      class="w-28 flex-none"
                      [value]="line.amount"
                      (input)="editFee($index, 'amount', $any($event.target).value)"
                    />
                    <button
                      appButton
                      variant="ghost"
                      size="sm"
                      type="button"
                      (click)="removeFee($index)"
                    >
                      Remove
                    </button>
                  </li>
                } @empty {
                  <li class="px-3 py-4 text-[13.5px] text-ink-muted">No charges added.</li>
                }
              </ul>

              <div class="flex flex-wrap items-center justify-between gap-3">
                <button appButton variant="secondary" size="sm" type="button" (click)="addFee()">
                  Add a charge
                </button>
                <p class="text-[14px]">
                  <span class="text-ink-muted">Total</span>
                  <span class="ml-2 text-[17px] tabular-nums">
                    Rs {{ feeTotal().toLocaleString() }}
                  </span>
                </p>
              </div>

              <div class="flex flex-wrap justify-between gap-3 border-t border-line pt-4">
                <button appButton variant="secondary" type="button" (click)="goTo(4)">Back</button>
                <button appButton variant="primary" type="button" (click)="finish()">
                  Finish admission
                </button>
              </div>
            </div>
          }
        </div>
      </div>
    </div>

    <app-modal
      [open]="done()"
      size="sm"
      heading="Admission complete"
      [description]="student() ? student()!.full_name + ' · ' + student()!.roll_no : ''"
      hasActions
      (closed)="done.set(false)"
    >
      <p class="measure">The file is saved. Fees were not — that endpoint does not exist yet.</p>
      <button appButton variant="secondary" modal-actions type="button" (click)="done.set(false)">
        Keep editing
      </button>
      <a appButton variant="primary" modal-actions routerLink="/students">Back to students</a>
    </app-modal>
  `,
})
export class NewStudent {
  private readonly students = inject(StudentsApi);
  private readonly sessionsApi = inject(SessionsApi);
  private readonly classesApi = inject(ClassesApi);
  private readonly subjectsApi = inject(SubjectsApi);
  private readonly enrollments = inject(EnrollmentsApi);
  private readonly router = inject(Router);

  /**
   * The file being edited, from `/students/:id/edit`.
   *
   * Absent on `/students/new`. Editing is the same five steps as admission —
   * the record, the enrollment and the password are the same three things
   * either way — so this page serves both rather than growing a second form
   * that would drift from it.
   */
  readonly id = input<string>();

  protected readonly input = INPUT;
  protected readonly select = SELECT;
  protected readonly steps = STEPS;
  protected readonly provinces = PROVINCES;
  protected readonly thisYear = String(new Date().getFullYear());

  protected readonly step = signal(1);
  protected readonly student = signal<Student | null>(null);
  protected readonly enrollment = signal<Enrollment | null>(null);
  protected readonly saving = signal(false);
  /** Cleared whenever the step changes, so it never outlives what it confirms. */
  protected readonly justSaved = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly done = signal(false);

  protected readonly sessions = signal<SessionRow[]>([]);
  protected readonly classes = signal<ClassRow[]>([]);
  protected readonly classSubjects = signal<Subject[]>([]);
  protected readonly classId = signal('');
  protected readonly chosenSubjects = signal<Set<string>>(new Set());

  /** This year's intake and the two before it, matched to any existing row. */
  protected readonly intakes = computed<IntakeOption[]>(() => {
    const current = new Date().getFullYear();
    const rows = this.sessions();
    return Array.from({ length: INTAKES_OFFERED }, (_, i) => {
      const start = current - i;
      return {
        start_year: start,
        label: `${start}-${start + 2}`,
        session: rows.find((s) => s.start_year === start) ?? null,
      };
    });
  });
  protected readonly intakeYear = signal(new Date().getFullYear());

  /** The id already fetched, so the load effect fires once per record. */
  private loadedId: string | null = null;

  /** The class is being changed on someone already enrolled elsewhere. */
  protected readonly movingClass = computed(() => {
    const current = this.enrollment();
    return !!current && !!this.classId() && current.class.id !== this.classId();
  });

  protected readonly fees = signal<FeeLine[]>([]);
  protected readonly feeTotal = computed(() =>
    this.fees().reduce((sum, line) => sum + (Number(line.amount) || 0), 0),
  );

  protected readonly record = inject(FormBuilder).nonNullable.group({
    first_name: ['', [Validators.required, Validators.maxLength(100)]],
    last_name: ['', [Validators.required, Validators.maxLength(100)]],
    b_form_cnic: [''],
    date_of_birth: [''],
    cell_no: [''],
    email: [''],
    father_name: [''],
    father_cnic: [''],
    mother_name: [''],
    guardian_cell_no: [''],
    address: [''],
    province: [''],
    domicile_district: [''],
    last_school_name: [''],
    ssc_roll_no: [''],
    ssc_year: [null as number | null],
    ssc_marks_obtained: [null as number | null],
    ssc_marks_total: [null as number | null],
  });

  protected readonly security = inject(FormBuilder).nonNullable.group({
    password: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128)]],
    confirm: ['', Validators.required],
  });

  constructor() {
    this.sessionsApi.list({ limit: 100 }).subscribe({
      next: (page) => this.sessions.set(page.items),
      error: () => this.sessions.set([]),
    });
    this.classesApi.list({ limit: 100 }).subscribe({
      next: (page) => this.classes.set(page.items),
      error: () => this.classes.set([]),
    });

    effect(() => {
      const id = this.id();
      // A plain field, not `student()`: reading the signal here would make
      // filling the page in re-run the effect that filled it.
      if (!id || id === this.loadedId) {
        return;
      }
      this.loadedId = id;
      this.students.get(id).subscribe({
        next: (saved) => this.accept(saved),
        error: (err: unknown) =>
          this.error.set(apiErrorMessage(err, 'Could not load this student.')),
      });
    });
  }

  /**
   * Fill the page in from a saved file.
   *
   * The enrollment is fetched separately and answers 404 when there is none —
   * an admitted student who has not been placed in a class yet is normal, not
   * an error, so that case leaves step 3 as it opens for a new admission.
   */
  private accept(saved: Student): void {
    this.student.set(saved);
    this.intakeYear.set(saved.session.start_year);
    this.record.reset({
      first_name: saved.first_name,
      last_name: saved.last_name,
      b_form_cnic: saved.b_form_cnic ?? '',
      date_of_birth: saved.date_of_birth ?? '',
      cell_no: saved.cell_no ?? '',
      email: saved.email ?? '',
      father_name: saved.father_name ?? '',
      father_cnic: saved.father_cnic ?? '',
      mother_name: saved.mother_name ?? '',
      guardian_cell_no: saved.guardian_cell_no ?? '',
      address: saved.address ?? '',
      province: saved.province ?? '',
      domicile_district: saved.domicile_district ?? '',
      last_school_name: saved.last_school_name ?? '',
      ssc_roll_no: saved.ssc_roll_no ?? '',
      ssc_year: saved.ssc_year,
      ssc_marks_obtained: saved.ssc_marks_obtained,
      ssc_marks_total: saved.ssc_marks_total,
    });

    if (!saved.enrollment) {
      return;
    }
    this.students.enrollment(saved.id).subscribe({
      next: (current) => {
        this.enrollment.set(current);
        // Sets the class and re-ticks the subjects this student already takes.
        this.chooseClass(current.class.id);
      },
      error: () => this.enrollment.set(null),
    });
  }

  // ----- the rail ----------------------------------------------------------
  protected readonly current = computed(() => STEPS.find((s) => s.n === this.step()) ?? STEPS[0]);

  /** Sign-in and fees are facts about a file, so they need one to exist. */
  protected reachable(s: StepDef): boolean {
    return s.n <= 3 || !!this.student();
  }

  /** A tick means what this step collects has been written down. */
  protected committed(s: StepDef): boolean {
    const saved = this.student();
    if (!saved) {
      return false;
    }
    switch (s.key) {
      case 'personal':
      case 'education':
        return true;
      case 'enrollment':
        return !!saved.enrollment;
      case 'security':
        return saved.has_password;
      default:
        return false;
    }
  }

  protected goTo(n: number): void {
    this.step.set(n);
    this.justSaved.set(false);
    this.error.set(null);
  }

  protected stepClasses(s: StepDef): string {
    const base =
      'flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-left transition-colors ' +
      'disabled:cursor-not-allowed disabled:opacity-45';
    return this.step() === s.n
      ? `${base} bg-sunken text-ink`
      : `${base} text-ink-muted hover:bg-sunken`;
  }

  /** Ticked, here, or still to come — the one thing a marker says. */
  private markerTone(s: StepDef): string {
    if (this.committed(s)) {
      return 'border-ok/40 bg-ok-soft text-ok';
    }
    return this.step() === s.n
      ? 'border-accent bg-accent text-on-accent'
      : 'border-line bg-surface text-ink-muted';
  }

  protected markerClasses(s: StepDef): string {
    const base =
      'flex h-6 w-6 flex-none items-center justify-center rounded-full border text-[12px]';
    return `${base} ${this.markerTone(s)}`;
  }

  /** The narrow-screen marker: a larger tap target, and it is the control. */
  protected dotClasses(s: StepDef): string {
    const base =
      'flex h-8 w-8 flex-none items-center justify-center rounded-full border text-[12.5px] ' +
      'transition-colors disabled:cursor-not-allowed disabled:opacity-45';
    return `${base} ${this.markerTone(s)}`;
  }

  // ----- the record: steps 1-2 --------------------------------------------
  protected namesMissing(): boolean {
    return this.record.controls.first_name.invalid || this.record.controls.last_name.invalid;
  }

  protected readonly sscPercentage = computed(() => {
    const { ssc_marks_obtained: got, ssc_marks_total: total } = this.record.getRawValue();
    return got && total ? Math.round(((got * 100) / total) * 100) / 100 : null;
  });

  /**
   * Details the API accepts, with blanks dropped.
   *
   * It rejects `''` where it wants a date, an email or a number, so an
   * untouched field is omitted rather than sent as an empty string.
   */
  private details(): Record<string, unknown> {
    return Object.fromEntries(
      Object.entries(this.record.getRawValue()).filter(
        ([, value]) => value !== '' && value !== null,
      ),
    );
  }

  /**
   * Save steps 1-2 and move on.
   *
   * Before the file exists there is nothing to save against — the intake has
   * not been chosen — so this only advances, and the values are written in one
   * call when Enrollment opens the file.
   */
  protected saveRecord(next: number): void {
    if (this.namesMissing()) {
      this.record.markAllAsTouched();
      return;
    }
    const existing = this.student();
    if (!existing) {
      this.goTo(next);
      return;
    }
    if (this.saving()) {
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    this.students.update(existing.id, this.details() as StudentUpdate).subscribe({
      next: (fresh) => {
        this.saving.set(false);
        this.justSaved.set(true);
        this.student.set(fresh);
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err, 'Could not save this student.'));
      },
    });
  }

  // ----- step 3: intake, class, subjects -----------------------------------
  protected chooseClass(id: string): void {
    this.classId.set(id);
    this.chosenSubjects.set(new Set());
    this.classSubjects.set([]);
    if (!id) {
      return;
    }
    this.subjectsApi.list({ class_id: id, limit: 100 }).subscribe({
      next: (page) => {
        this.classSubjects.set(page.items);
        // Re-tick what this student already takes, if they are staying put.
        const current = this.enrollment();
        if (current && current.class.id === id) {
          this.chosenSubjects.set(new Set(current.subjects.map((s) => s.id)));
        }
      },
      error: () => this.classSubjects.set([]),
    });
  }

  protected toggleSubject(id: string): void {
    const next = new Set(this.chosenSubjects());
    if (!next.delete(id)) {
      next.add(id);
    }
    this.chosenSubjects.set(next);
  }

  protected enrolButtonLabel(): string {
    if (!this.student()) {
      return this.classId() ? 'Open file and enrol' : 'Open file';
    }
    if (!this.enrollment()) {
      return 'Enrol';
    }
    return this.movingClass() ? 'Move class' : 'Save subjects';
  }

  /**
   * The one call that opens the file, and the enrollment that follows it.
   *
   * The intake row may not exist — nobody has admitted into that year yet — so
   * it is opened first. `sessions:create` is a super-admin grant, so a teacher
   * choosing a fresh year gets a plain 403 rather than a silent failure.
   */
  protected saveEnrollment(): void {
    if (this.saving()) {
      return;
    }
    if (this.namesMissing()) {
      this.error.set('A first and last name are needed before the file can be opened.');
      return;
    }
    this.saving.set(true);
    this.error.set(null);

    const existing = this.student();
    const open$ = existing ? of(existing) : this.openFile();

    open$
      .pipe(
        switchMap((opened) => this.applyEnrollment(opened)),
        switchMap((opened) => this.students.get(opened.id)),
      )
      .subscribe({
        next: (fresh) => {
          this.saving.set(false);
          this.justSaved.set(true);
          this.student.set(fresh);
        },
        error: (err: unknown) => {
          this.saving.set(false);
          this.error.set(apiErrorMessage(err, 'Could not save this enrollment.'));
        },
      });
  }

  private openFile(): Observable<Student> {
    const intake = this.intakes().find((i) => i.start_year === this.intakeYear());
    const session$ = intake?.session
      ? of(intake.session)
      : this.sessionsApi.create({ start_year: this.intakeYear() });

    return session$.pipe(
      switchMap((session) => {
        // Keep the new row, so re-saving does not try to create it twice.
        if (!this.sessions().some((s) => s.id === session.id)) {
          this.sessions.set([session, ...this.sessions()]);
        }
        return this.students.create({
          ...this.details(),
          session_id: session.id,
        } as unknown as StudentCreate);
      }),
      // Hold the record the moment it exists. If the enrollment that follows
      // is refused — a full subject answers 409 — the file is still open, and
      // pressing again must not try to admit the same person twice.
      tap((opened) => {
        this.student.set(opened);
        // The URL becomes the record's, so a reload or a shared link lands on
        // the file rather than on a blank admission form.
        this.loadedId = opened.id;
        void this.router.navigate(['/students', opened.id, 'edit'], { replaceUrl: true });
      }),
    );
  }

  /** Enrol, move, or replace the subject picks — whichever this is. */
  private applyEnrollment(saved: Student): Observable<Student> {
    const classId = this.classId();
    const current = this.enrollment();
    const subjectIds = [...this.chosenSubjects()];

    if (!classId) {
      return of(saved);
    }

    let request: Observable<Enrollment>;
    if (!current) {
      request = this.enrollments.create({
        student_id: saved.id,
        class_id: classId,
        subject_ids: subjectIds,
      });
    } else if (current.class.id !== classId) {
      // A move drops every pick, so the new class's subjects are set after it.
      request = this.enrollments
        .move(current.id, classId)
        .pipe(switchMap((moved) => this.enrollments.setSubjects(moved.enrollment.id, subjectIds)));
    } else {
      request = this.enrollments.setSubjects(current.id, subjectIds);
    }

    return request.pipe(
      switchMap((result) => {
        this.enrollment.set(result);
        return of(saved);
      }),
    );
  }

  // ----- step 4: portal sign-in -------------------------------------------
  protected mismatch(): boolean {
    const { password, confirm } = this.security.getRawValue();
    return !!confirm && password !== confirm;
  }

  protected savePassword(): void {
    const saved = this.student();
    if (!saved || this.security.invalid || this.mismatch() || this.saving()) {
      this.security.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    this.students.setPassword(saved.id, this.security.getRawValue().password).subscribe({
      next: (fresh) => {
        this.saving.set(false);
        this.justSaved.set(true);
        this.student.set(fresh);
        this.security.reset();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err, 'Could not set this password.'));
      },
    });
  }

  // ----- step 5: interface only -------------------------------------------
  protected addFee(): void {
    this.fees.set([...this.fees(), { description: '', amount: 0 }]);
  }

  protected editFee(index: number, key: keyof FeeLine, value: string): void {
    const next = [...this.fees()];
    next[index] = {
      ...next[index],
      [key]: key === 'amount' ? Number(value) || 0 : value,
    };
    this.fees.set(next);
  }

  protected removeFee(index: number): void {
    this.fees.set(this.fees().filter((_, i) => i !== index));
  }

  protected finish(): void {
    if (this.student()) {
      this.done.set(true);
    } else {
      void this.router.navigate(['/students']);
    }
  }
}
