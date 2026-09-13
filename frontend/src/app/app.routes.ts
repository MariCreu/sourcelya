import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  // This app is app.sourcelya.com — the authenticated application only.
  // Marketing/landing content lives at sourcelya.com (see web/), a separate
  // static site, not a route in here. `/` just sends visitors to log in.
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login/login.component').then((m) => m.LoginComponent)
  },
  {
    path: 'signup',
    loadComponent: () =>
      import('./features/auth/signup/signup.component').then((m) => m.SignupComponent)
  },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent)
  },
  {
    path: 'suppliers',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/suppliers/suppliers.component').then((m) => m.SuppliersComponent)
  },
  {
    path: 'products',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/products/products.component').then((m) => m.ProductsComponent)
  },
  {
    path: 'products/:productId',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/products/product-detail/product-detail.component').then(
        (m) => m.ProductDetailComponent
      )
  },
  {
    path: 'requests',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/requests/requests.component').then((m) => m.RequestsComponent)
  },
  {
    path: 'requests/new',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/requests/new-request/new-request.component').then(
        (m) => m.NewRequestComponent
      )
  },
  {
    path: 'requests/:requestId',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/requests/request-detail/request-detail.component').then(
        (m) => m.RequestDetailComponent
      )
  },
  {
    // The supplier's public portal — deliberately NOT behind authGuard and
    // NOT using TopNavComponent: a supplier never logs in (see FASE 3
    // spec), so this route must never render the authenticated app's nav.
    path: 'request/:token',
    loadComponent: () =>
      import('./features/public-request/public-request.component').then(
        (m) => m.PublicRequestComponent
      )
  },
  { path: '**', redirectTo: '' }
];
