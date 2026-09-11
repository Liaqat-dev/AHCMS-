import { HttpClient } from "@angular/common/http";
import { Component, inject, signal } from "@angular/core";

import { environment } from "../../../environments/environment";
import { apiErrorMessage } from "../../core/api-error";
import { Student, TokenService } from "../../core/auth/token.service";

@Component({
  selector: "app-profile",
  template: `
    <section>
      <h1 class="text-2xl font-semibold">My profile</h1>

      @if (error()) {
        <p
          class="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
          role="alert"
        >
          {{ error() }}
        </p>
      }

      @if (student(); as me) {
        <dl
          class="mt-6 divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white"
        >
          <div class="flex justify-between px-4 py-3">
            <dt class="text-sm text-slate-500">Roll number</dt>
            <dd class="text-sm font-medium">{{ me.roll_no }}</dd>
          </div>
          <div class="flex justify-between px-4 py-3">
            <dt class="text-sm text-slate-500">Name</dt>
            <dd class="text-sm font-medium">{{ me.full_name }}</dd>
          </div>
          <div class="flex justify-between px-4 py-3">
            <dt class="text-sm text-slate-500">Email</dt>
            <dd class="text-sm font-medium">{{ me.email ?? "Not on file" }}</dd>
          </div>
        </dl>
      } @else if (loading()) {
        <p class="mt-4 text-sm text-slate-600">Loading…</p>
      }

      <p class="mt-6 text-sm text-slate-500">
        Courses, enrollments, and results appear here once those endpoints
        exist.
      </p>
    </section>
  `,
})
export class Profile {
  private readonly http = inject(HttpClient);

  // Seeded from the token response so the page paints immediately, then
  // confirmed against the API — which also proves the bearer token works.
  protected readonly student = signal<Student | null>(
    inject(TokenService).student(),
  );
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.http.get<Student>(`${environment.apiUrl}/student/me`).subscribe({
      next: (me) => {
        this.student.set(me);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err, "Could not load your profile."));
      },
    });
  }
}
