import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BRAND } from '../../core/brand';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.scss'
})
export class LandingComponent {
  readonly brand = BRAND;
}
