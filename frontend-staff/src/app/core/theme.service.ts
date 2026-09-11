import { DOCUMENT, Injectable, effect, inject, signal } from '@angular/core';

/** What the user picked. `system` follows the OS and keeps following it. */
export type ThemePreference = 'light' | 'dark' | 'system';

/** What is actually on screen once `system` is resolved. */
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'cms.theme';

/**
 * Light/dark preference, applied as a `dark` class on `<html>`.
 *
 * A class rather than `prefers-color-scheme` alone, so an explicit choice
 * beats the OS. The preference is remembered per browser; it is a display
 * setting, not account data, so it never goes near the API.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly media = this.document.defaultView?.matchMedia('(prefers-color-scheme: dark)');

  /** The stored choice. */
  readonly preference = signal<ThemePreference>(this.read());

  /** Tracks the OS while the preference is `system`. */
  private readonly systemPrefersDark = signal(this.media?.matches ?? false);

  /** What is on screen: the preference, with `system` resolved. */
  readonly theme = signal<ResolvedTheme>('light');

  constructor() {
    this.media?.addEventListener('change', (event) => this.systemPrefersDark.set(event.matches));

    effect(() => {
      const preference = this.preference();
      const resolved: ResolvedTheme =
        preference === 'system' ? (this.systemPrefersDark() ? 'dark' : 'light') : preference;

      this.theme.set(resolved);
      this.document.documentElement.classList.toggle('dark', resolved === 'dark');
    });
  }

  set(preference: ThemePreference): void {
    this.preference.set(preference);
    try {
      this.document.defaultView?.localStorage.setItem(STORAGE_KEY, preference);
    } catch {
      // Private browsing, or storage disabled. The theme still applies for
      // this visit; only remembering it is lost.
    }
  }

  /** Flip to the opposite of what is currently on screen. */
  toggle(): void {
    this.set(this.theme() === 'dark' ? 'light' : 'dark');
  }

  private read(): ThemePreference {
    try {
      const stored = this.document.defaultView?.localStorage.getItem(STORAGE_KEY);
      if (stored === 'light' || stored === 'dark' || stored === 'system') {
        return stored;
      }
    } catch {
      // Same as above — fall through to following the OS.
    }
    return 'system';
  }
}
