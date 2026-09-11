import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { apiErrorMessage } from '../../core/api-error';
import { PermissionRow, Role } from '../../core/api/domain';
import { RolesApi } from '../../core/api/services';
import { Permission } from '../../core/auth/permissions';
import { TokenService } from '../../core/auth/token.service';
import { Badge } from '../../shared/ui/badge';
import { Button } from '../../shared/ui/button';
import { INPUT } from '../../shared/ui/controls';
import { Field } from '../../shared/ui/field';
import { Modal } from '../../shared/ui/modal';
import { PageHeader } from '../../shared/ui/page-header';

/**
 * Column order: the order the actions happen in, not alphabetical — a `delete`
 * column between `create` and `update` reads as an accident. Anything not
 * listed here follows, sorted.
 */
const ACTION_ORDER = ['read', 'create', 'update', 'delete'];

interface Cell {
  action: string;
  code: string;
  description: string | null;
}

interface ResourceGroup {
  resource: string;
  label: string;
  cells: Cell[];
}

/** "academic sessions" reads better than "sessions" beside "students". */
const RESOURCE_LABELS: Record<string, string> = {
  sessions: 'Academic sessions',
  users: 'Staff accounts',
  roles: 'Roles & permissions',
};

/**
 * Roles — who can do what.
 *
 * The permission catalog is a fixed set of `resource:action` codes, so the page
 * is a grid of resources against actions rather than a flat list of checkboxes.
 * The question an administrator actually has is "can teachers mark attendance?"
 * — a row per resource answers it at a glance, and the shape of the grid is the
 * shape of the codes rather than a layout invented for it.
 *
 * Reaching this page at all needs `roles:read`, which ships only with
 * `super_admin`; the sidebar hides it for everyone else and the API enforces
 * the same rule. `super_admin` itself is a system role and cannot be edited —
 * otherwise an administrator could revoke their own ability to administer.
 */
@Component({
  selector: 'app-roles',
  imports: [ReactiveFormsModule, Badge, Button, Field, Modal, PageHeader],
  template: `
    <div class="space-y-6">
      <app-page-header
        heading="Roles"
        description="A role is a named set of permissions. Staff accounts hold roles; changes take effect on the person's next sign-in."
      >
        @if (canCreate()) {
          <button appButton variant="primary" type="button" actions (click)="startCreate()">
            New role
          </button>
        }
      </app-page-header>

      @if (error(); as message) {
        <p
          class="rounded-panel border border-danger/25 bg-danger-soft px-4 py-3 text-[14px] text-danger"
          role="alert"
        >
          {{ message }}
        </p>
      }

      <div class="grid gap-5 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <!-- Roles. A row on a phone, a column on a desktop. -->
        <nav aria-label="Roles">
          <ul
            class="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:gap-1 lg:overflow-visible lg:pb-0"
          >
            @for (role of roles(); track role.id) {
              <li class="flex-none lg:flex-auto">
                <button
                  type="button"
                  [class]="roleClasses(role)"
                  [attr.aria-current]="selected()?.id === role.id"
                  (click)="select(role)"
                >
                  <span class="flex items-center gap-2">
                    <span class="truncate text-[14px]">{{ role.name }}</span>
                    @if (role.is_system) {
                      <app-badge tone="neutral">system</app-badge>
                    }
                  </span>
                  <span class="mt-0.5 block text-[12.5px] text-ink-muted">
                    {{ role.permissions.length }} of {{ permissions().length }} permissions
                  </span>
                </button>
              </li>
            }
          </ul>
        </nav>

        <!-- The grid -->
        @if (selected(); as role) {
          <section class="rounded-panel border border-line bg-surface">
            <header
              class="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b
                     border-line px-5 py-3.5"
            >
              <div class="min-w-0">
                <h2 class="text-[17px] leading-6">{{ role.name }}</h2>
                <p class="mt-0.5 text-[13px] text-ink-muted">
                  {{ role.description || 'No description' }}
                </p>
              </div>
              @if ((canUpdate() || canDelete()) && !role.is_system) {
                <div class="flex flex-none items-center gap-2">
                  @if (canUpdate()) {
                    <button
                      appButton
                      variant="ghost"
                      size="sm"
                      type="button"
                      (click)="startRename(role)"
                    >
                      Rename
                    </button>
                  }
                  @if (canDelete()) {
                    <button
                      appButton
                      variant="ghost"
                      size="sm"
                      type="button"
                      (click)="confirm.set(role)"
                    >
                      Delete
                    </button>
                  }
                </div>
              }
            </header>

            @if (role.is_system) {
              <p class="border-b border-line bg-sunken px-5 py-2.5 text-[13px] text-ink-muted">
                A system role. It cannot be renamed, deleted, or have permissions removed — without
                it, nobody could administer roles at all.
              </p>
            } @else if (canUpdate()) {
              <div
                class="flex flex-wrap items-center justify-between gap-3 border-b border-line
                       bg-sunken px-5 py-2.5"
              >
                <div class="flex items-center gap-2">
                  <button
                    appButton
                    variant="ghost"
                    size="sm"
                    type="button"
                    (click)="selectAll(true)"
                  >
                    Select all
                  </button>
                  <button
                    appButton
                    variant="ghost"
                    size="sm"
                    type="button"
                    (click)="selectAll(false)"
                  >
                    Clear
                  </button>
                </div>
                <div class="flex items-center gap-3">
                  @if (dirty()) {
                    <span class="text-[13px] text-ink-muted">Unsaved changes</span>
                  }
                  <button
                    appButton
                    variant="primary"
                    size="sm"
                    type="button"
                    [disabled]="!dirty()"
                    [loading]="saving()"
                    (click)="savePermissions()"
                  >
                    Save permissions
                  </button>
                </div>
              </div>
            }

            <div class="overflow-x-auto">
              <table class="w-full border-collapse text-[14px]">
                <thead>
                  <tr>
                    <th
                      class="border-b border-line bg-sunken px-5 py-2.5 text-left text-[12.5px]
                             font-medium text-ink-muted"
                      scope="col"
                    >
                      Resource
                    </th>
                    @for (action of actions(); track action) {
                      <th
                        class="w-24 border-b border-line bg-sunken px-4 py-2.5 text-left
                               text-[12.5px] font-medium text-ink-muted"
                        scope="col"
                      >
                        {{ action }}
                      </th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (group of groups(); track group.resource) {
                    <tr class="hover:bg-sunken">
                      <th
                        class="border-b border-line-soft px-5 py-2.5 text-left font-normal"
                        scope="row"
                      >
                        {{ group.label }}
                      </th>
                      @for (action of actions(); track action) {
                        <td class="border-b border-line-soft px-4 py-2.5">
                          @if (cellFor(group, action); as cell) {
                            <label class="flex cursor-pointer items-center gap-2">
                              <input
                                type="checkbox"
                                class="accent-accent"
                                [checked]="chosen().has(cell.code)"
                                [disabled]="!canUpdate() || role.is_system"
                                [attr.aria-label]="cell.description || cell.code"
                                (change)="toggle(cell.code)"
                              />
                              <span class="sr-only">{{ cell.code }}</span>
                            </label>
                          } @else {
                            <span class="text-ink-faint" aria-hidden="true">–</span>
                          }
                        </td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </section>
        } @else if (loaded()) {
          <p
            class="rounded-panel border border-line bg-surface px-5 py-10 text-center text-[14px] text-ink-muted"
          >
            Choose a role to see what it can do.
          </p>
        }
      </div>
    </div>

    <!-- Create / rename -->
    <app-modal
      [open]="editing() !== null"
      [heading]="editing()?.id ? 'Rename role' : 'New role'"
      hasActions
      (closed)="editing.set(null)"
    >
      <form class="space-y-4" [formGroup]="form" (ngSubmit)="saveRole()">
        <app-field
          label="Name"
          for="role-name"
          hint="Lower case, digits and underscores — this is an identifier, not a title."
          [error]="nameError()"
        >
          <input
            id="role-name"
            [class]="input"
            formControlName="name"
            placeholder="head_of_department"
          />
        </app-field>
        <app-field label="Description" for="role-desc">
          <input id="role-desc" [class]="input" formControlName="description" />
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
        (click)="saveRole()"
      >
        {{ editing()?.id ? 'Save changes' : 'Create role' }}
      </button>
    </app-modal>

    <!-- Delete -->
    <app-modal
      [open]="confirm() !== null"
      size="sm"
      heading="Delete this role?"
      [description]="confirm()?.name ?? ''"
      hasActions
      (closed)="confirm.set(null)"
    >
      <p class="measure">
        Anyone holding it loses these permissions at their next sign-in. A role that is still
        assigned to someone cannot be deleted.
      </p>
      @if (deleteError()) {
        <p class="mt-3 text-[13px] text-danger" role="alert">{{ deleteError() }}</p>
      }

      <button appButton variant="secondary" modal-actions type="button" (click)="confirm.set(null)">
        Keep role
      </button>
      <button
        appButton
        variant="danger"
        modal-actions
        type="button"
        [loading]="deleting()"
        (click)="remove()"
      >
        Delete role
      </button>
    </app-modal>
  `,
})
export class Roles {
  private readonly api = inject(RolesApi);
  private readonly tokens = inject(TokenService);

  protected readonly input = INPUT;

  protected readonly roles = signal<Role[]>([]);
  protected readonly permissions = signal<PermissionRow[]>([]);
  protected readonly selected = signal<Role | null>(null);
  protected readonly loaded = signal(false);

  /** Working copy of the selected role's permission codes. */
  protected readonly chosen = signal<Set<string>>(new Set());
  private original = new Set<string>();

  protected readonly editing = signal<Partial<Role> | null>(null);
  protected readonly confirm = signal<Role | null>(null);
  protected readonly saving = signal(false);
  protected readonly deleting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly deleteError = signal<string | null>(null);

  protected readonly canCreate = computed(() => this.tokens.has(Permission.RolesCreate));
  protected readonly canUpdate = computed(() => this.tokens.has(Permission.RolesUpdate));
  protected readonly canDelete = computed(() => this.tokens.has(Permission.RolesDelete));

  /** Every action in the catalog, `read` and `write` first. */
  protected readonly actions = computed(() => {
    const found = new Set(this.permissions().map((p) => p.code.split(':')[1]));
    const ordered = ACTION_ORDER.filter((a) => found.has(a));
    return [...ordered, ...[...found].filter((a) => !ACTION_ORDER.includes(a)).sort()];
  });

  /** One row per resource, which is what the codes are already grouped by. */
  protected readonly groups = computed<ResourceGroup[]>(() => {
    const map = new Map<string, ResourceGroup>();
    for (const permission of this.permissions()) {
      const [resource, action] = permission.code.split(':');
      let group = map.get(resource);
      if (!group) {
        group = {
          resource,
          label: RESOURCE_LABELS[resource] ?? this.titleCase(resource),
          cells: [],
        };
        map.set(resource, group);
      }
      group.cells.push({ action, code: permission.code, description: permission.description });
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label));
  });

  protected readonly dirty = computed(() => {
    const chosen = this.chosen();
    return chosen.size !== this.original.size || [...chosen].some((c) => !this.original.has(c));
  });

  protected readonly nameError = computed(() => {
    const control = this.form.controls.name;
    return control.value && control.invalid
      ? 'Lower case letters, digits and underscores only.'
      : null;
  });

  protected readonly form = inject(FormBuilder).nonNullable.group({
    name: ['', [Validators.required, Validators.pattern(/^[a-z0-9_]+$/), Validators.maxLength(64)]],
    description: [''],
  });

  constructor() {
    this.api.permissions().subscribe({
      next: (rows) => this.permissions.set(rows),
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'Could not load the permission catalog.')),
    });
    this.load();
  }

  private load(selectId?: string): void {
    this.api.list().subscribe({
      next: (roles) => {
        this.roles.set(roles);
        this.loaded.set(true);
        const keep = selectId ?? this.selected()?.id;
        const next = roles.find((r) => r.id === keep) ?? roles[0];
        if (next) {
          this.select(next);
        }
      },
      error: (err: unknown) => {
        this.loaded.set(true);
        this.error.set(apiErrorMessage(err, 'Could not load roles.'));
      },
    });
  }

  protected select(role: Role): void {
    this.selected.set(role);
    this.chosen.set(new Set(role.permissions));
    this.original = new Set(role.permissions);
  }

  protected roleClasses(role: Role): string {
    const base =
      'w-full min-w-[11rem] rounded-control border px-3 py-2 text-left transition-colors lg:min-w-0';
    return this.selected()?.id === role.id
      ? `${base} border-accent-line bg-accent-soft text-ink`
      : `${base} border-line bg-surface text-ink-muted hover:bg-sunken hover:text-ink`;
  }

  protected cellFor(group: ResourceGroup, action: string): Cell | undefined {
    return group.cells.find((cell) => cell.action === action);
  }

  protected toggle(code: string): void {
    const next = new Set(this.chosen());
    if (!next.delete(code)) {
      next.add(code);
    }
    this.chosen.set(next);
  }

  protected selectAll(on: boolean): void {
    this.chosen.set(on ? new Set(this.permissions().map((p) => p.code)) : new Set());
  }

  protected savePermissions(): void {
    const role = this.selected();
    if (!role || !this.dirty() || this.saving()) {
      return;
    }
    this.saving.set(true);
    this.error.set(null);

    this.api.setPermissions(role.id, [...this.chosen()]).subscribe({
      next: (updated) => {
        this.saving.set(false);
        this.roles.set(this.roles().map((r) => (r.id === updated.id ? updated : r)));
        this.select(updated);
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err, 'Could not save these permissions.'));
      },
    });
  }

  protected startCreate(): void {
    this.form.reset({ name: '', description: '' });
    this.formError.set(null);
    this.editing.set({});
  }

  protected startRename(role: Role): void {
    this.form.reset({ name: role.name, description: role.description ?? '' });
    this.formError.set(null);
    this.editing.set(role);
  }

  protected saveRole(): void {
    if (this.form.invalid || this.saving()) {
      return;
    }
    const current = this.editing();
    const { name, description } = this.form.getRawValue();
    const body = { name, description: description || null };
    this.saving.set(true);
    this.formError.set(null);

    const request = current?.id ? this.api.update(current.id, body) : this.api.create(body);
    request.subscribe({
      next: (role) => {
        this.saving.set(false);
        this.editing.set(null);
        this.load(role.id);
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.formError.set(apiErrorMessage(err, 'Could not save this role.'));
      },
    });
  }

  protected remove(): void {
    const role = this.confirm();
    if (!role || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.deleteError.set(null);

    this.api.remove(role.id).subscribe({
      next: () => {
        this.deleting.set(false);
        this.confirm.set(null);
        this.selected.set(null);
        this.load();
      },
      error: (err: unknown) => {
        this.deleting.set(false);
        this.deleteError.set(apiErrorMessage(err, 'Could not delete this role.'));
      },
    });
  }

  private titleCase(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ');
  }
}
