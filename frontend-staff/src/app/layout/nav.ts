import { Route, Router, Routes } from '@angular/router';

/**
 * Navigation metadata, declared on the route itself.
 *
 * The sidebar is built by reading the router config, so a route is the only
 * place a section is defined: add a child route under the shell with a `nav`
 * block and it appears in the sidebar, guarded by the same permission. Keeping
 * a second hand-maintained list beside the routes is how a nav ends up
 * pointing at a page that no longer exists.
 */
export interface NavMeta {
  label: string;
  /** Key into `NAV_ICONS`. Falls back to a dot when unknown. */
  icon?: string;
  /**
   * Permission required to see *and* open the route. `navGuard` reads this, so
   * the code is written once rather than repeated in a `canActivate`.
   */
  permission?: string;
  /** Optional heading this item sits under. Ungrouped items come first. */
  group?: string;
}

export interface NavItem extends NavMeta {
  path: string;
}

export interface NavGroup {
  /** Null for the leading, unlabelled group. */
  heading: string | null;
  items: NavItem[];
}

/** Route `data` shape the sidebar looks for. */
export interface NavRouteData {
  nav?: NavMeta;
}

/**
 * The shell's children that declare `data.nav`, in route order.
 *
 * Reads the live router config rather than a copy, so it stays correct however
 * the routes are reorganised.
 */
export function navItems(router: Router): NavItem[] {
  const shell = findShellRoute(router.config);
  return (shell?.children ?? [])
    .filter((route): route is Route & { path: string; data: NavRouteData } =>
      Boolean(route.path && (route.data as NavRouteData | undefined)?.nav),
    )
    .map((route) => ({ path: route.path, ...(route.data.nav as NavMeta) }));
}

/** Group consecutive items by heading, keeping ungrouped ones at the top. */
export function groupNav(items: NavItem[]): NavGroup[] {
  const groups: NavGroup[] = [];
  for (const item of items) {
    const heading = item.group ?? null;
    const last = groups.at(-1);
    if (last && last.heading === heading) {
      last.items.push(item);
    } else {
      groups.push({ heading, items: [item] });
    }
  }
  return groups;
}

/** The route that hosts the shell: the one whose children are the sections. */
function findShellRoute(routes: Routes): Route | undefined {
  return routes.find((route) => route.path === '' && route.children?.length);
}

/**
 * Line icons, 24×24, stroked in `currentColor`.
 *
 * Drawn from the objects the sections are about — a ruled register, a lectern,
 * a marked calendar — rather than generic glyphs, so the sidebar reads at a
 * glance once it is collapsed to icons alone.
 */
export const NAV_ICONS: Record<string, string> = {
  dashboard: 'M4 4h6v7H4zM14 4h6v4h-6zM14 12h6v8h-6zM4 15h6v5H4z',
  students:
    'M9 11a3.2 3.2 0 100-6.4 3.2 3.2 0 000 6.4M3 20a6 6 0 0112 0M17.5 11a2.8 2.8 0 100-5.6M17 20h4a4.6 4.6 0 00-3.4-4.4',
  faculty: 'M4 4.5h16v10.5H4zM12 15v4.5M8.5 19.5h7M8 8.5h8M8 11.5h5',
  enrollments: 'M6.5 3.5h11v17h-11zM6.5 8h11M10 12h5M10 15.5h5M8 12h.01M8 15.5h.01',
  attendance: 'M4 6.5h16V20H4zM8 3.5v4M16 3.5v4M4 10.5h16M9 15l2 2 4-4',
  programs: 'M12 4l9 4.5-9 4.5-9-4.5zM6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5',
  subjects: 'M4 5.5A2.5 2.5 0 016.5 3H19v15H6.5A2.5 2.5 0 004 20.5zM4 5.5v15M9 7.5h6',
  users: 'M12 11.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7M5 20a7 7 0 0114 0',
  roles: 'M12 3.5l7 3v5c0 4-3 7.3-7 8.5-4-1.2-7-4.5-7-8.5v-5zM9.5 12l1.8 1.8 3.7-3.7',
};

export const NAV_ICON_FALLBACK = 'M12 9.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5';
