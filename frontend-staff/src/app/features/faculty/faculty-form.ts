import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { apiErrorMessage } from '../../core/api-error';
import { Faculty as FacultyRow, StaffUserRow } from '../../core/api/domain';
import { FacultyApi, StaffUsersApi } from '../../core/api/services';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT, SELECT } from '../../shared/ui/controls';
import { Field } from '../../shared/ui/field';

/** Common ladder in a Pakistani college; free text, so anything else is fine. */
const DESIGNATIONS = [
  'Lecturer',
  'Assistant Professor',
  'Associate Professor',
  'Professor',
  'Lab Assistant',
  'Visiting Faculty',
];

type TabKey = 'personal' | 'qualifications' | 'salary';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'personal', label: 'Personal info' },
  { key: 'qualifications', label: 'Qualifications' },
  { key: 'salary', label: 'Salary' },
];

interface Degree {
  title: string;
  institution: string;
  year: string;
}

interface PayLine {
  label: string;
  amount: number;
}

/**
 * A faculty member's file, on its own page.
 *
 * **Tabs, not steps.** The student admission form is numbered because an
 * admission happens in an order — you cannot enrol someone who does not exist
 * yet. A personnel file has no such order: qualifications and salary are
 * facets of one record, and someone editing an existing member goes straight
 * to the one they came for. Everything else matches the admission page, so the
 * two read as the same kind of screen.
 *
 * Personal info and Qualifications save to the API. Salary has no endpoint and
 * says so rather than appearing to store anything.
 */
@Component({
  selector: 'app-faculty-form',
  imports: [ReactiveFormsModule, RouterLink, Badge, Button, Field],
  template: `
    <div class="space-y-6">
      <div class="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div class="min-w-0">
          <a routerLink="/faculty" class="text-[13px] text-ink-muted hover:text-ink">Faculty</a>
          <h1 class="mt-0.5 text-[26px] leading-tight">
            {{ member() ? member()!.full_name : 'Add faculty' }}
          </h1>
          @if (member(); as saved) {
            <p class="mt-1 flex flex-wrap items-center gap-2 text-[14px] text-ink-muted">
              <app-badge tone="accent">{{ saved.employee_no }}</app-badge>
              @if (saved.designation) {
                <span>{{ saved.designation }}</span>
              }
              @if (!saved.is_active) {
                <app-badge tone="neutral">Former</app-badge>
              }
              @if (saved.missing_fields.length) {
                <app-badge tone="warn">{{ saved.missing_fields.length }} outstanding</app-badge>
              }
            </p>
          } @else {
            <p class="measure mt-1 text-[14px] text-ink-muted">
              An employee number and a name open the file. The rest can be filled in now or later.
            </p>
          }
        </div>
        <a appButton variant="secondary" routerLink="/faculty">
          {{ member() ? 'Done' : 'Cancel' }}
        </a>
      </div>

      @if (loadError()) {
        <p
          class="rounded-panel border border-danger/25 bg-danger-soft px-4 py-3 text-[14px] text-danger"
          role="alert"
        >
          {{ loadError() }}
        </p>
      } @else {
        <div>
          <!-- Tabs scroll rather than wrap on a phone, so the row stays one line -->
          <div role="tablist" class="-mb-px flex gap-1 overflow-x-auto border-b border-line">
            @for (tab of tabs; track tab.key) {
              <button
                type="button"
                role="tab"
                [attr.aria-selected]="active() === tab.key"
                [disabled]="tab.key !== 'personal' && !member()"
                [class]="tabClasses(tab.key)"
                (click)="active.set(tab.key)"
              >
                {{ tab.label }}
              </button>
            }
          </div>

          <div class="rounded-b-panel rounded-tr-panel border border-t-0 border-line bg-surface">
            <!-- Personal info -->
            @if (active() === 'personal') {
              <form class="space-y-5 p-5" [formGroup]="form" (ngSubmit)="save()">
                <div class="grid gap-4 sm:grid-cols-2">
                  <app-field label="Employee number" for="emp-no" hint="As it appears on the file.">
                    <input
                      id="emp-no"
                      [class]="input"
                      formControlName="employee_no"
                      placeholder="EMP-001"
                    />
                  </app-field>
                  @if (member()) {
                    <app-field label="Status" for="fac-status">
                      <select id="fac-status" [class]="select" formControlName="is_active">
                        <option [value]="true">Current</option>
                        <option [value]="false">Former</option>
                      </select>
                    </app-field>
                  }
                  <app-field label="First name" for="fac-first">
                    <input id="fac-first" [class]="input" formControlName="first_name" />
                  </app-field>
                  <app-field label="Last name" for="fac-last">
                    <input id="fac-last" [class]="input" formControlName="last_name" />
                  </app-field>
                </div>

                <hr class="border-line" />

                <div class="grid gap-4 sm:grid-cols-2">
                  <app-field label="CNIC" for="fac-cnic" hint="13 digits; dashes optional.">
                    <input
                      id="fac-cnic"
                      [class]="input"
                      formControlName="cnic"
                      placeholder="42101-1234567-1"
                    />
                  </app-field>
                  <app-field label="Cell number" for="fac-cell">
                    <input
                      id="fac-cell"
                      [class]="input"
                      formControlName="cell_no"
                      placeholder="0300 1234567"
                    />
                  </app-field>
                  <app-field label="Email" for="fac-email">
                    <input id="fac-email" type="email" [class]="input" formControlName="email" />
                  </app-field>
                  <app-field label="Joined on" for="joined">
                    <input id="joined" type="date" [class]="input" formControlName="joined_on" />
                  </app-field>
                  <!-- What makes "only this subject's teacher may enter its
                       marks" answerable: the request carries a staff account,
                       the subject names a faculty member, and this joins them. -->
                  <app-field
                    label="Sign-in account"
                    for="fac-user"
                    hint="Needed before they can enter marks for the subjects they teach."
                  >
                    <select id="fac-user" [class]="select" formControlName="user_id">
                      <option value="">Not linked</option>
                      @for (account of accounts(); track account.id) {
                        <option [value]="account.id">
                          {{ account.full_name || account.email }}
                        </option>
                      }
                    </select>
                  </app-field>
                </div>

                <app-field label="Address" for="fac-address">
                  <textarea
                    id="fac-address"
                    rows="2"
                    [class]="input"
                    formControlName="address"
                  ></textarea>
                </app-field>

                @if (error()) {
                  <p class="text-[13px] text-danger" role="alert">{{ error() }}</p>
                }

                <div class="flex justify-end border-t border-line pt-4">
                  <button
                    appButton
                    variant="primary"
                    type="submit"
                    [disabled]="form.invalid"
                    [loading]="saving()"
                  >
                    {{ member() ? 'Save changes' : 'Create record' }}
                  </button>
                </div>
              </form>
            }

            <!-- Qualifications -->
            @if (active() === 'qualifications') {
              <form class="space-y-5 p-5" [formGroup]="form" (ngSubmit)="save()">
                <div class="grid gap-4 sm:grid-cols-2">
                  <app-field label="Designation" for="designation" hint="Their post here.">
                    <input
                      id="designation"
                      [class]="input"
                      formControlName="designation"
                      list="designations"
                      placeholder="Lecturer"
                    />
                    <datalist id="designations">
                      @for (title of designations; track title) {
                        <option [value]="title"></option>
                      }
                    </datalist>
                  </app-field>
                  <app-field
                    label="Highest qualification"
                    for="qualification"
                    hint="The one that appears on the staff list."
                  >
                    <input
                      id="qualification"
                      [class]="input"
                      formControlName="qualification"
                      placeholder="MPhil Mathematics"
                    />
                  </app-field>
                </div>

                @if (error()) {
                  <p class="text-[13px] text-danger" role="alert">{{ error() }}</p>
                }

                <div class="flex justify-end border-t border-line pt-4">
                  <button appButton variant="primary" type="submit" [loading]="saving()">
                    Save changes
                  </button>
                </div>

                <hr class="border-line" />

                <div>
                  <h2 class="text-[15px]">Further degrees</h2>
                  <div class="mt-2 rounded-control border border-warn/30 bg-warn-soft px-4 py-3">
                    <p class="text-[13.5px] text-warn">
                      Not stored yet. The record holds one qualification; a list of degrees needs a
                      table of its own, which does not exist.
                    </p>
                  </div>

                  <ul class="mt-3 rounded-control border border-line">
                    @for (degree of degrees(); track $index) {
                      <li
                        class="grid gap-2 border-b border-line-soft p-3 last:border-b-0
                               sm:grid-cols-[1fr_1fr_6rem_auto] sm:items-center"
                      >
                        <input
                          [class]="input"
                          placeholder="MSc Physics"
                          [value]="degree.title"
                          (input)="editDegree($index, 'title', $any($event.target).value)"
                        />
                        <input
                          [class]="input"
                          placeholder="University of the Punjab"
                          [value]="degree.institution"
                          (input)="editDegree($index, 'institution', $any($event.target).value)"
                        />
                        <input
                          [class]="input"
                          placeholder="2014"
                          [value]="degree.year"
                          (input)="editDegree($index, 'year', $any($event.target).value)"
                        />
                        <button
                          appButton
                          variant="ghost"
                          size="sm"
                          type="button"
                          (click)="removeDegree($index)"
                        >
                          Remove
                        </button>
                      </li>
                    } @empty {
                      <li class="px-3 py-4 text-[13.5px] text-ink-muted">No degrees listed.</li>
                    }
                  </ul>

                  <button
                    appButton
                    variant="secondary"
                    size="sm"
                    type="button"
                    class="mt-3"
                    (click)="addDegree()"
                  >
                    Add a degree
                  </button>
                </div>
              </form>
            }

            <!-- Salary -->
            @if (active() === 'salary') {
              <div class="space-y-5 p-5">
                <div class="rounded-control border border-warn/30 bg-warn-soft px-4 py-3">
                  <p class="text-[13.5px] text-warn">
                    Not stored yet. There is no payroll endpoint — this is the shape of the screen,
                    not a working salary sheet.
                  </p>
                </div>

                <ul class="rounded-control border border-line">
                  @for (line of pay(); track $index) {
                    <li
                      class="flex items-center gap-3 border-b border-line-soft px-3 py-2
                             last:border-b-0"
                    >
                      <input
                        [class]="input"
                        class="flex-1"
                        placeholder="Basic pay"
                        [value]="line.label"
                        (input)="editPay($index, 'label', $any($event.target).value)"
                      />
                      <input
                        type="number"
                        [class]="input"
                        class="max-w-[9rem]"
                        [value]="line.amount"
                        (input)="editPay($index, 'amount', $any($event.target).value)"
                      />
                      <button
                        appButton
                        variant="ghost"
                        size="sm"
                        type="button"
                        (click)="removePay($index)"
                      >
                        Remove
                      </button>
                    </li>
                  } @empty {
                    <li class="px-3 py-4 text-[13.5px] text-ink-muted">Nothing added.</li>
                  }
                </ul>

                <div class="flex flex-wrap items-center justify-between gap-3">
                  <button appButton variant="secondary" size="sm" type="button" (click)="addPay()">
                    Add a line
                  </button>
                  <p class="text-[14px]">
                    <span class="text-ink-muted">Monthly total</span>
                    <span class="ml-2 text-[17px]">Rs {{ payTotal().toLocaleString() }}</span>
                  </p>
                </div>
              </div>
            }
          </div>
        </div>
      }
    </div>
  `,
})
export class FacultyForm {
  /** Route param; absent when adding. Bound by `withComponentInputBinding()`. */
  readonly id = input<string>();

  private readonly api = inject(FacultyApi);
  private readonly usersApi = inject(StaffUsersApi);
  private readonly router = inject(Router);

  protected readonly input = INPUT;
  protected readonly select = SELECT;
  protected readonly tabs = TABS;
  protected readonly designations = DESIGNATIONS;

  protected readonly active = signal<TabKey>('personal');
  protected readonly member = signal<FacultyRow | null>(null);
  protected readonly accounts = signal<StaffUserRow[]>([]);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly loadError = signal<string | null>(null);

  protected readonly degrees = signal<Degree[]>([]);
  protected readonly pay = signal<PayLine[]>([]);
  protected readonly payTotal = computed(() =>
    this.pay().reduce((sum, line) => sum + (Number(line.amount) || 0), 0),
  );

  protected readonly form = inject(FormBuilder).nonNullable.group({
    employee_no: ['', [Validators.required, Validators.maxLength(32)]],
    first_name: ['', [Validators.required, Validators.maxLength(100)]],
    last_name: ['', [Validators.required, Validators.maxLength(100)]],
    designation: [''],
    qualification: [''],
    cnic: [''],
    email: [''],
    cell_no: [''],
    address: [''],
    joined_on: [''],
    user_id: [''],
    is_active: [true],
  });

  constructor() {
    // Only staff accounts can be linked; a teacher who never signs in has none.
    this.usersApi.list({ limit: 100 }).subscribe({
      next: (page) => this.accounts.set(page.items),
      error: () => this.accounts.set([]),
    });

    effect(() => {
      const id = this.id();
      if (!id) {
        return;
      }
      this.api.get(id).subscribe({
        next: (member) => this.accept(member),
        error: (err: unknown) =>
          this.loadError.set(apiErrorMessage(err, 'Could not load this record.')),
      });
    });
  }

  protected tabClasses(key: TabKey): string {
    const base =
      'relative whitespace-nowrap rounded-t-panel border border-b-0 px-4 py-2 text-[14px] ' +
      'transition-colors disabled:cursor-not-allowed disabled:opacity-45';
    return this.active() === key
      ? `${base} border-line bg-surface text-ink`
      : `${base} border-transparent text-ink-muted hover:text-ink`;
  }

  protected save(): void {
    if (this.form.invalid || this.saving()) {
      return;
    }
    const current = this.member();
    const raw = this.form.getRawValue();

    // The API rejects '' where it wants a date, an email or a CNIC. On create
    // those fields are dropped; on edit a cleared field must be sent as null,
    // or clearing something would silently do nothing.
    const body = Object.fromEntries(
      Object.entries(raw)
        .filter(([, value]) => current || (value !== '' && value !== null))
        .map(([key, value]) => [key, value === '' ? null : value]),
    ) as Record<string, unknown>;
    for (const key of ['employee_no', 'first_name', 'last_name']) {
      body[key] = raw[key as 'employee_no'];
    }
    body['is_active'] = String(raw.is_active) === 'true';

    this.saving.set(true);
    this.error.set(null);

    const request = current ? this.api.update(current.id, body) : this.api.create(body);
    request.subscribe({
      next: (saved) => {
        this.saving.set(false);
        this.accept(saved);
        // A new record now has an id, so the URL should be its own: a reload
        // or a shared link lands on the record rather than a blank form.
        if (!current) {
          void this.router.navigate(['/faculty', saved.id, 'edit'], { replaceUrl: true });
        }
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err, 'Could not save this record.'));
      },
    });
  }

  // ----- interface-only tabs ----------------------------------------------
  protected addDegree(): void {
    this.degrees.set([...this.degrees(), { title: '', institution: '', year: '' }]);
  }

  protected editDegree(index: number, key: keyof Degree, value: string): void {
    const next = [...this.degrees()];
    next[index] = { ...next[index], [key]: value };
    this.degrees.set(next);
  }

  protected removeDegree(index: number): void {
    this.degrees.set(this.degrees().filter((_, i) => i !== index));
  }

  protected addPay(): void {
    this.pay.set([...this.pay(), { label: '', amount: 0 }]);
  }

  protected editPay(index: number, key: keyof PayLine, value: string): void {
    const next = [...this.pay()];
    next[index] = { ...next[index], [key]: key === 'amount' ? Number(value) || 0 : value };
    this.pay.set(next);
  }

  protected removePay(index: number): void {
    this.pay.set(this.pay().filter((_, i) => i !== index));
  }

  private accept(member: FacultyRow): void {
    this.member.set(member);
    this.form.reset({
      employee_no: member.employee_no,
      first_name: member.first_name,
      last_name: member.last_name,
      designation: member.designation ?? '',
      qualification: member.qualification ?? '',
      cnic: member.cnic ?? '',
      email: member.email ?? '',
      cell_no: member.cell_no ?? '',
      address: member.address ?? '',
      joined_on: member.joined_on ?? '',
      user_id: member.user_id ?? '',
      is_active: member.is_active,
    });
  }
}
