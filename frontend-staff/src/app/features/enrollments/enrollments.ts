import { Component } from '@angular/core';

import { Card } from '../../shared/ui/card';

@Component({
  selector: 'app-enrollments',
  imports: [Card],
  template: `
    <div class="space-y-6">
      <h1 class="text-[26px] leading-tight">Enrollments</h1>
      <app-card variant="quiet">
        <p class="measure text-[14.5px] text-ink-muted">
          Class enrollment and subject choices land here. The API is ready — /api/v1/enrollments,
          one class per student with optional subjects.
        </p>
      </app-card>
    </div>
  `,
})
export class Enrollments {}
