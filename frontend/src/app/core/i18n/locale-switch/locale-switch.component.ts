import { Component, inject } from '@angular/core';
import { LocaleService } from '../locale.service';

@Component({
  selector: 'app-locale-switch',
  standalone: true,
  templateUrl: './locale-switch.component.html',
  styleUrl: './locale-switch.component.scss'
})
export class LocaleSwitchComponent {
  private readonly localeService = inject(LocaleService);

  readonly locale = this.localeService.locale;

  select(locale: 'es' | 'en'): void {
    this.localeService.setLocale(locale);
  }
}
