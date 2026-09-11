import { Routes } from '@angular/router';

import { Permission } from './core/auth/permissions';
import { navGuard, requirePermission, staffGuard } from './core/auth/staff.guard';

/**
 * Staff routes (teachers and administrators). Students have their own
 * application in `frontend-portal/` and never reach any of this.
 *
 * Every feature is lazy-loaded; the domain sections render inside the shared
 * shell, and the auth pages render standalone.
 *
 * `data.nav` is what puts a section in the sidebar (see `layout/nav.ts`) and
 * also what `navGuard` reads for the permission — so adding a section is
 * adding a route here, and the permission is written once.
 */
export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./layout/shell/shell').then((m) => m.Shell),
    canActivate: [staffGuard],
    canActivateChild: [navGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        data: { nav: { label: 'Dashboard', icon: 'dashboard' } },
        loadComponent: () => import('./features/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'students',
        data: {
          nav: { label: 'Students', icon: 'students', permission: Permission.StudentsRead },
        },
        loadComponent: () => import('./features/students/students').then((m) => m.Students),
      },
      {
        // No `nav` block: this is reached from the Students page, and a
        // sidebar entry for a form would be a second way in to the same task.
        path: 'students/new',
        canActivate: [requirePermission(Permission.StudentsCreate)],
        loadComponent: () => import('./features/students/new-student').then((m) => m.NewStudent),
      },
      {
        // The same five steps, opened on a file that already exists: editing a
        // record is correcting the things admission collected, not a different
        // form.
        path: 'students/:id/edit',
        canActivate: [requirePermission(Permission.StudentsUpdate)],
        loadComponent: () => import('./features/students/new-student').then((m) => m.NewStudent),
      },
      {
        path: 'faculty',
        data: { nav: { label: 'Faculty', icon: 'faculty', permission: Permission.FacultyRead } },
        loadComponent: () => import('./features/faculty/faculty').then((m) => m.Faculty),
      },
      {
        // Reached from the Faculty page; no `nav` block, so no sidebar entry.
        path: 'faculty/new',
        canActivate: [requirePermission(Permission.FacultyCreate)],
        loadComponent: () => import('./features/faculty/faculty-form').then((m) => m.FacultyForm),
      },
      {
        path: 'faculty/:id/edit',
        canActivate: [requirePermission(Permission.FacultyUpdate)],
        loadComponent: () => import('./features/faculty/faculty-form').then((m) => m.FacultyForm),
      },
      {
        path: 'programs',
        data: {
          nav: { label: 'Programs', icon: 'programs', permission: Permission.ProgramsRead },
        },
        loadComponent: () => import('./features/programs/programs').then((m) => m.Programs),
      },
      {
        path: 'classes',
        data: { nav: { label: 'Classes', icon: 'subjects', permission: Permission.ClassesRead } },
        loadComponent: () => import('./features/classes/classes').then((m) => m.Classes),
      },
      {
        path: 'subjects',
        data: {
          nav: { label: 'Subjects', icon: 'enrollments', permission: Permission.SubjectsRead },
        },
        loadComponent: () => import('./features/subjects/subjects').then((m) => m.Subjects),
      },
      {
        path: 'attendance',
        data: {
          nav: { label: 'Attendance', icon: 'attendance', permission: Permission.AttendanceRead },
        },
        loadComponent: () => import('./features/attendance/attendance').then((m) => m.Attendance),
      },
      {
        path: 'exams',
        data: { nav: { label: 'Exams', icon: 'exams', permission: Permission.ExamsRead } },
        loadComponent: () => import('./features/exams/exams').then((m) => m.Exams),
      },
      {
        // Reached from the Exams list; no `nav` block, so no sidebar entry.
        path: 'exams/:id',
        canActivate: [requirePermission(Permission.MarksRead)],
        loadComponent: () => import('./features/exams/exam-detail').then((m) => m.ExamDetail),
      },
      {
        // Administration. `roles:read` ships only with super_admin, so the
        // sidebar entry appears for administrators and nobody else — and
        // navGuard turns the same code into the route guard.
        path: 'roles',
        data: { nav: { label: 'Roles', icon: 'roles', permission: Permission.RolesRead } },
        loadComponent: () => import('./features/roles/roles').then((m) => m.Roles),
      },
      {
        path: 'enrollments',
        data: {
          nav: {
            label: 'Enrollments',
            icon: 'enrollments',
            permission: Permission.EnrollmentsRead,
          },
        },
        loadComponent: () =>
          import('./features/enrollments/enrollments').then((m) => m.Enrollments),
      },
    ],
  },
  {
    path: 'auth',
    loadChildren: () => import('./features/auth/auth.routes').then((m) => m.authRoutes),
  },
  { path: '**', redirectTo: '' },
];
