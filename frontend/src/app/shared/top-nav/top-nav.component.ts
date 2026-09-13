import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { BRAND } from '../../core/brand';
import { LocaleSwitchComponent } from '../../core/i18n/locale-switch/locale-switch.component';
import { LocaleService } from '../../core/i18n/locale.service';

@Component({
  selector: 'app-top-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, LocaleSwitchComponent],
  templateUrl: './top-nav.component.html',
  styleUrl: './top-nav.component.scss'
})
export class TopNavComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly localeService = inject(LocaleService);

  readonly brand = BRAND;
  readonly t = this.localeService.t;

  async logout(): Promise<void> {
    await this.authService.signOut();
    await this.router.navigateByUrl('/login');
  }
}
