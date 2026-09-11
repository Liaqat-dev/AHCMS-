import { Component, booleanAttribute, computed, input, output } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { NAV_ICON_FALLBACK, NAV_ICONS, NavGroup, NavItem, groupNav } from './nav';

/**
 * The section list, shared by the desktop sidebar and the small-screen panel.
 *
 * One list rendered twice rather than two lists to keep in step: the only
 * difference is `collapsed`, which the panel never sets.
 */
@Component({
  selector: 'app-nav-list',
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav [attr.aria-label]="ariaLabel()">
      @for (group of groups(); track group.heading) {
        @if (group.heading) {
          <!-- Headings only exist when routes declare a group, and are dropped
               entirely when the sidebar is collapsed to icons. -->
          @if (!collapsed()) {
            <p class="mt-5 mb-1 px-3 text-[12px] font-medium text-ink-faint first:mt-0">
              {{ group.heading }}
            </p>
          } @else {
            <hr class="my-2 border-line" />
          }
        }

        <ul class="space-y-0.5">
          @for (item of group.items; track item.path) {
            <li>
              <!-- The active bar carries no resting colour on purpose: a
                   transparent default out-orders the accent in Tailwind's
                   generated CSS (same specificity, Tailwind picks the order),
                   so the marker would never paint. -->
              <a
                [routerLink]="item.path"
                routerLinkActive="bg-sunken text-ink before:bg-accent"
                [routerLinkActiveOptions]="{ exact: false }"
                [title]="collapsed() ? item.label : null"
                (click)="navigated.emit()"
                class="relative flex items-center gap-3 rounded-control py-2 text-[14px]
                       text-ink-muted transition-colors before:absolute before:top-1.5
                       before:bottom-1.5 before:left-0 before:w-0.5 before:rounded-full
                       hover:bg-sunken hover:text-ink"
                [class]="collapsed() ? 'justify-center px-0' : 'px-3'"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  class="flex-none"
                  aria-hidden="true"
                >
                  <path
                    [attr.d]="iconFor(item)"
                    stroke="currentColor"
                    stroke-width="1.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                @if (!collapsed()) {
                  <span class="truncate">{{ item.label }}</span>
                }
              </a>
            </li>
          }
        </ul>
      }
    </nav>
  `,
})
export class NavList {
  readonly items = input.required<NavItem[]>();
  readonly collapsed = input(false, { transform: booleanAttribute });
  readonly ariaLabel = input('Sections');

  /** Fired on any link click, so the small-screen panel can close itself. */
  readonly navigated = output<void>();

  protected readonly groups = computed<NavGroup[]>(() => groupNav(this.items()));

  protected iconFor(item: NavItem): string {
    return (item.icon && NAV_ICONS[item.icon]) || NAV_ICON_FALLBACK;
  }
}
