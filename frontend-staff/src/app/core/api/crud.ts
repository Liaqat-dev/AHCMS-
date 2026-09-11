import { HttpClient, HttpParams } from '@angular/common/http';
import { inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Page } from '../models/api';

/** Query values a list endpoint accepts; empty ones are dropped. */
export type Query = Record<string, string | number | null | undefined>;

export function toParams(query: Query): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(query)) {
    // '' is a cleared filter, not a filter for the empty string.
    if (value !== null && value !== undefined && value !== '') {
      params = params.set(key, String(value));
    }
  }
  return params;
}

/**
 * The five calls every collection in this API supports, in one place.
 *
 * The endpoints are uniform — paged list with filters, get, create, patch,
 * delete, all under `/api/v1/<path>` — so each domain service is a path, its
 * types, and whatever is genuinely its own.
 */
export abstract class CrudApi<TRow, TCreate, TUpdate> {
  protected readonly http = inject(HttpClient);
  /** Collection path, without a leading slash: `programs`, `classes`, … */
  protected abstract readonly path: string;

  protected get base(): string {
    return `${environment.apiUrl}/${this.path}`;
  }

  list(query: Query = {}): Observable<Page<TRow>> {
    return this.http.get<Page<TRow>>(this.base, { params: toParams(query) });
  }

  get(id: string): Observable<TRow> {
    return this.http.get<TRow>(`${this.base}/${id}`);
  }

  create(body: TCreate): Observable<TRow> {
    return this.http.post<TRow>(this.base, body);
  }

  update(id: string, body: TUpdate): Observable<TRow> {
    return this.http.patch<TRow>(`${this.base}/${id}`, body);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }
}
