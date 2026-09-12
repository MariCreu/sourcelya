import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../auth/auth.service';

/**
 * Waits for the initial Supabase session check to finish before deciding,
 * so a hard refresh on /dashboard doesn't bounce a logged-in user to
 * /login just because the session hasn't loaded from storage yet.
 */
export const authGuard: CanActivateFn = async () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.initialized()) {
    await new Promise<void>((resolve) => {
      const check = () => {
        if (authService.initialized()) {
          resolve();
        } else {
          setTimeout(check, 25);
        }
      };
      check();
    });
  }

  if (authService.isAuthenticated) {
    return true;
  }

  return router.createUrlTree(['/login']);
};
