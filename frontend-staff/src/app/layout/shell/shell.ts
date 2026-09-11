import { DOCUMENT, Component, computed, effect, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { TokenService } from '../../core/auth/token.service';
import { Button } from '../../shared/ui/button';
import { ThemeToggle } from '../../shared/ui/theme-toggle';
import { NavList } from '../nav-list';
import { navItems } from '../nav';

const COLLAPSED_KEY = 'cms.sidebar.collapsed';

/**
 * App shell: a full-width navbar with a sidebar beneath it.
 *
 * The sidebar's sections come from the router config (see `layout/nav.ts`), so
 * adding a route with `data.nav` adds a section — there is no second list to
 * keep in step.
 *
 * Below `lg` the sidebar is not a drawer over the page but a panel that opens
 * directly under the navbar, pushing the content down. On a phone that keeps
 * the page's own scroll position intact and never traps the reader behind a
 * scrim they have to find their way out of.
 */
@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, Button, ThemeToggle, NavList],
  template: `
    <div class="min-h-screen bg-canvas text-ink">
      <header class="sticky top-0 z-30 border-b border-line bg-surface">
        <div class="flex h-14 items-center gap-3 px-3 sm:px-4">
          <button
            type="button"
            class="flex h-9 w-9 flex-none items-center justify-center rounded-control
                   text-ink-muted transition-colors hover:bg-sunken hover:text-ink lg:hidden"
            [attr.aria-expanded]="panelOpen()"
            aria-controls="nav-panel"
            [attr.aria-label]="panelOpen() ? 'Close sections' : 'Open sections'"
            (click)="panelOpen.set(!panelOpen())"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              @if (panelOpen()) {
                <path
                  d="M5 5l14 14M19 5L5 19"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                />
              } @else {
                <path
                  d="M4 7h16M4 12h16M4 17h16"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                />
              }
            </svg>
          </button>

          <a routerLink="/dashboard" class="font-display text-[19px] leading-none text-ink">
            College MS
          </a>

          <div class="flex flex-1 items-center justify-end gap-2 sm:gap-3">
            <span class="hidden text-[13.5px] text-ink-muted sm:inline">{{ displayName() }}</span>
            <app-theme-toggle />
            <button appButton variant="secondary" size="sm" type="button" (click)="signOut()">
              Sign out
            </button>
          </div>
        </div>

        <!-- Small screens: the sidebar's contents, under the navbar. -->
        @if (panelOpen()) {
          <div id="nav-panel" class="border-t border-line px-3 py-2 lg:hidden">
            <app-nav-list
              [items]="visibleItems()"
              ariaLabel="Sections"
              (navigated)="panelOpen.set(false)"
            />
          </div>
        }
      </header>

      <div class="flex">
        <aside
          class="sticky top-14 hidden h-[calc(100vh-3.5rem)] flex-none flex-col border-r
                 border-line bg-surface transition-[width] duration-150 lg:flex"
          [class]="collapsed() ? 'w-16' : 'w-60'"
        >
          <div class="flex-1 overflow-y-auto px-2 py-3">
            <app-nav-list [items]="visibleItems()" [collapsed]="collapsed()" />
          </div>

          <div class="border-t border-line p-2">
            <button
              type="button"
              class="flex w-full items-center gap-3 rounded-control px-3 py-2 text-[13.5px]
                     text-ink-muted transition-colors hover:bg-sunken hover:text-ink"
              [class]="collapsed() ? 'justify-center px-0' : ''"
              [attr.aria-label]="collapsed() ? 'Expand sidebar' : 'Collapse sidebar'"
              (click)="toggleCollapsed()"
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
                  [attr.d]="collapsed() ? 'M10 6l6 6-6 6' : 'M14 6l-6 6 6 6'"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              @if (!collapsed()) {
                <span>Collapse</span>
              }
            </button>
          </div>
        </aside>

        <main class="min-w-0 flex-1 px-4 py-7 sm:px-6 sm:py-8">
          <router-outlet />
        </main>
      </div>
    </div>
  `,
  host: {
    // Escape closes the small-screen panel, the way it closes any other
    // temporarily-open thing in the app.
    '(document:keydown.escape)': 'panelOpen.set(false)',
  },
})
export class Shell {
  private readonly tokens = inject(TokenService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);

  /** Sections declared by the routes, in route order. */
  private readonly allItems = navItems(this.router);

  /** Hide what this user cannot open; `navGuard` enforces the same rule. */
  protected readonly visibleItems = computed(() =>
    this.allItems.filter((item) => !item.permission || this.tokens.has(item.permission)),
  );

  protected readonly collapsed = signal(this.readCollapsed());
  protected readonly panelOpen = signal(false);

  protected readonly displayName = computed(() => {
    const user = this.tokens.user();
    return user?.full_name?.trim() || user?.email || '';
  });

  constructor() {
    // A redirect or a link elsewhere in the page can navigate without the
    // panel's own click handler running.
    this.router.events
      .pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe(() => this.panelOpen.set(false));

    effect(() => {
      const collapsed = this.collapsed();
      try {
        this.document.defaultView?.localStorage.setItem(COLLAPSED_KEY, String(collapsed));
      } catch {
        // Storage unavailable; the choice simply lasts this visit.
      }
    });
  }

  protected toggleCollapsed(): void {
    this.collapsed.set(!this.collapsed());
  }

  protected signOut(): void {
    this.auth.logout().subscribe(() => void this.router.navigate(['/auth/login']));
  }

  private readCollapsed(): boolean {
    try {
      return this.document.defaultView?.localStorage.getItem(COLLAPSED_KEY) === 'true';
    } catch {
      return false;
    }
  }
}
