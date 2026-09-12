import { Component, inject } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterOutlet } from '@angular/router';
import { BRAND } from './core/brand';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  constructor() {
    inject(Title).setTitle(BRAND.name);
  }
}
