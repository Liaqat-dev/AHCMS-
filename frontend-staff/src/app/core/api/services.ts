import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { CrudApi } from './crud';
import {
  AttendanceSheet,
  AttendanceSummary,
  Enrollment,
  EnrollmentCreate,
  EnrollmentMoveResult,
  Exam,
  ExamCreate,
  ExamPaper,
  ExamUpdate,
  ExamMarkInput,
  MarkSheet,
  Faculty,
  FacultyWrite,
  PermissionRow,
  Role,
  StaffUserRow,
  RoleCreate,
  RoleUpdate,
  SessionRow,
  Student,
  StudentCreate,
  StudentUpdate,
  ClassCreate,
  ClassRow,
  ClassUpdate,
  MarkInput,
  Program,
  ProgramWrite,
  Subject,
  SubjectCreate,
  SubjectUpdate,
} from './domain';

@Injectable({ providedIn: 'root' })
export class ProgramsApi extends CrudApi<Program, ProgramWrite, Partial<ProgramWrite>> {
  protected readonly path = 'programs';
}

@Injectable({ providedIn: 'root' })
export class ClassesApi extends CrudApi<ClassRow, ClassCreate, ClassUpdate> {
  protected readonly path = 'classes';
}

@Injectable({ providedIn: 'root' })
export class SubjectsApi extends CrudApi<Subject, SubjectCreate, SubjectUpdate> {
  protected readonly path = 'subjects';

  /** Replace the whole set of classes this subject is taught to. */
  setClasses(id: string, classIds: string[]): Observable<Subject> {
    return this.http.put<Subject>(`${this.base}/${id}/classes`, { class_ids: classIds });
  }
}

@Injectable({ providedIn: 'root' })
export class AttendanceApi extends CrudApi<
  AttendanceSummary,
  { class_id: string; date?: string },
  never
> {
  protected readonly path = 'attendance';

  /** The full register, with every eligible student and their mark. */
  sheet(id: string): Observable<AttendanceSheet> {
    return this.http.get<AttendanceSheet>(`${this.base}/${id}`);
  }

  /** The register for a class on a date — 404 when the class did not meet. */
  forClassOn(classId: string, date: string): Observable<AttendanceSheet> {
    return this.http.get<AttendanceSheet>(
      `${environment.apiUrl}/classes/${classId}/attendance/${date}`,
    );
  }

  /** Mark only the students named. `status: null` clears a mark. */
  mark(id: string, marks: MarkInput[]): Observable<AttendanceSheet> {
    return this.http.patch<AttendanceSheet>(`${this.base}/${id}`, { marks });
  }

  /** Save the whole register; students omitted go back to unmarked. */
  replace(id: string, marks: MarkInput[]): Observable<AttendanceSheet> {
    return this.http.put<AttendanceSheet>(`${this.base}/${id}`, { marks });
  }

  open(classId: string, date?: string): Observable<AttendanceSheet> {
    return this.http.post<AttendanceSheet>(this.base, { class_id: classId, date });
  }
}

@Injectable({ providedIn: 'root' })
export class StudentsApi extends CrudApi<Student, StudentCreate, StudentUpdate> {
  protected readonly path = 'students';

  /** The student's class and chosen subjects. 404 when not enrolled. */
  enrollment(id: string): Observable<Enrollment> {
    return this.http.get<Enrollment>(`${this.base}/${id}/enrollment`);
  }

  /**
   * Issue or replace the portal password.
   *
   * Separate from `update` because it is a different act: everything else on
   * the record is a correction, this hands somebody the ability to sign in.
   */
  setPassword(id: string, password: string): Observable<Student> {
    return this.http.put<Student>(`${this.base}/${id}/password`, { password });
  }
}

@Injectable({ providedIn: 'root' })
export class SessionsApi extends CrudApi<SessionRow, { start_year: number }, never> {
  protected readonly path = 'sessions';
}

@Injectable({ providedIn: 'root' })
export class EnrollmentsApi extends CrudApi<Enrollment, EnrollmentCreate, never> {
  protected readonly path = 'enrollments';

  /**
   * Move the student to another class.
   *
   * Not `update`: the response is the enrollment *plus* how many subjects the
   * move dropped, so it does not have the shape the base class assumes.
   */
  move(id: string, classId: string): Observable<EnrollmentMoveResult> {
    return this.http.patch<EnrollmentMoveResult>(`${this.base}/${id}`, { class_id: classId });
  }

  /** Replace the subjects this student takes. An empty list means none. */
  setSubjects(id: string, subjectIds: string[]): Observable<Enrollment> {
    return this.http.put<Enrollment>(`${this.base}/${id}/subjects`, { subject_ids: subjectIds });
  }
}

@Injectable({ providedIn: 'root' })
export class FacultyApi extends CrudApi<Faculty, FacultyWrite, FacultyWrite> {
  protected readonly path = 'faculty';
}

/**
 * Roles and the permission catalog.
 *
 * Not a `CrudApi`: roles are a short, unpaged list — a college has a handful,
 * and paging them would only hide the comparison the page exists to make.
 */
@Injectable({ providedIn: 'root' })
export class RolesApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/roles`;

  list(): Observable<Role[]> {
    return this.http.get<Role[]>(this.base);
  }

  /** The fixed catalog of `resource:action` codes. */
  permissions(): Observable<PermissionRow[]> {
    return this.http.get<PermissionRow[]>(`${this.base}/permissions`);
  }

  create(body: RoleCreate): Observable<Role> {
    return this.http.post<Role>(this.base, body);
  }

  update(id: string, body: RoleUpdate): Observable<Role> {
    return this.http.patch<Role>(`${this.base}/${id}`, body);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  /** Replace the whole set this role carries. */
  setPermissions(id: string, permissions: string[]): Observable<Role> {
    return this.http.put<Role>(`${this.base}/${id}/permissions`, { permissions });
  }
}

@Injectable({ providedIn: 'root' })
export class ExamsApi extends CrudApi<Exam, ExamCreate, ExamUpdate> {
  protected readonly path = 'exams';

  /** The mark sheet for one paper, and whether this caller may edit it. */
  marks(paperId: string): Observable<MarkSheet> {
    return this.http.get<MarkSheet>(`${this.base}/papers/${paperId}/marks`);
  }

  /** Record marks for the students named; others are left alone. */
  setMarks(paperId: string, marks: ExamMarkInput[]): Observable<MarkSheet> {
    return this.http.put<MarkSheet>(`${this.base}/papers/${paperId}/marks`, { marks });
  }

  setPaperTotal(paperId: string, totalMarks: number): Observable<ExamPaper> {
    return this.http.patch<ExamPaper>(`${this.base}/papers/${paperId}`, {
      total_marks: totalMarks,
    });
  }
}

@Injectable({ providedIn: 'root' })
export class StaffUsersApi extends CrudApi<StaffUserRow, never, never> {
  protected readonly path = 'users';
}
