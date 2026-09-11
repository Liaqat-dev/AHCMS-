/**
 * Permission codes, mirroring backend `app/core/permissions.py`.
 * Used only to hide UI a user cannot act on; the API is the real check.
 */
export const Permission = {
  // Actions are read / create / update / delete. A code exists only where an
  // endpoint backs it — students and staff accounts are deactivated rather
  // than deleted, and an academic session is write-once.
  StudentsRead: 'students:read',
  StudentsCreate: 'students:create',
  StudentsUpdate: 'students:update',

  FacultyRead: 'faculty:read',
  FacultyCreate: 'faculty:create',
  FacultyUpdate: 'faculty:update',
  FacultyDelete: 'faculty:delete',

  ProgramsRead: 'programs:read',
  ProgramsCreate: 'programs:create',
  ProgramsUpdate: 'programs:update',
  ProgramsDelete: 'programs:delete',

  ClassesRead: 'classes:read',
  ClassesCreate: 'classes:create',
  ClassesUpdate: 'classes:update',
  ClassesDelete: 'classes:delete',

  SubjectsRead: 'subjects:read',
  SubjectsCreate: 'subjects:create',
  SubjectsUpdate: 'subjects:update',
  SubjectsDelete: 'subjects:delete',

  EnrollmentsRead: 'enrollments:read',
  EnrollmentsCreate: 'enrollments:create',
  EnrollmentsUpdate: 'enrollments:update',
  EnrollmentsDelete: 'enrollments:delete',

  AttendanceRead: 'attendance:read',
  AttendanceCreate: 'attendance:create',
  AttendanceUpdate: 'attendance:update',
  AttendanceDelete: 'attendance:delete',

  SessionsRead: 'sessions:read',
  SessionsCreate: 'sessions:create',

  UsersRead: 'users:read',
  UsersCreate: 'users:create',
  UsersUpdate: 'users:update',

  ExamsRead: 'exams:read',
  ExamsCreate: 'exams:create',
  ExamsUpdate: 'exams:update',
  ExamsDelete: 'exams:delete',

  // Marks are the one place ownership matters as well as permission: the API
  // also checks that you teach the subject, via faculty.user_id.
  MarksRead: 'marks:read',
  MarksUpdate: 'marks:update',
  MarksUpdateAny: 'marks:update_any',

  RolesRead: 'roles:read',
  RolesCreate: 'roles:create',
  RolesUpdate: 'roles:update',
  RolesDelete: 'roles:delete',
} as const;

export type PermissionCode = (typeof Permission)[keyof typeof Permission];
