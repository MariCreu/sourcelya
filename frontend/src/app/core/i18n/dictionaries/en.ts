import { Dictionary } from './types';

export const en: Dictionary = {
  nav: {
    dashboard: 'Dashboard',
    suppliers: 'Suppliers',
    products: 'Products',
    logout: 'Log out'
  },

  statusLabels: {
    green: 'Complete',
    orange: 'Missing information',
    red: 'Review required'
  },

  auth: {
    login: {
      title: 'Log in',
      emailLabel: 'Email',
      passwordLabel: 'Password',
      submit: 'Log in',
      submitting: 'Logging in…',
      switchPrompt: "Don't have an account?",
      switchLink: 'Start free',
      genericError: 'Could not log in.'
    },
    signup: {
      title: 'Start free',
      emailLabel: 'Email',
      passwordLabel: 'Password',
      submit: 'Create account',
      submitting: 'Creating account…',
      switchPrompt: 'Already have an account?',
      switchLink: 'Log in',
      genericError: 'Could not sign up.',
      confirmationTitle: 'Check your email',
      confirmationBody: (email: string) =>
        `We sent a confirmation link to ${email}. Confirm it, then log in to set up Sourcelya.`,
      goToLogin: 'Go to login'
    }
  },

  onboarding: {
    title: 'Set up your company',
    subtitle: 'One last step before you can invite suppliers.',
    companyNameLabel: 'Company name',
    countryLabel: 'Country',
    countryPlaceholder: 'e.g. NL',
    submit: 'Create company',
    submitting: 'Creating…',
    genericError: 'Could not create the company. Check the fields and try again.',
    loadError: 'Could not load your account.'
  },

  suppliers: {
    pageTitle: 'Suppliers',
    addButton: 'Add supplier',
    cancelButton: 'Cancel',
    loading: 'Loading…',
    loadError: 'Could not load suppliers.',
    empty: 'No suppliers yet. Add your first one to start requesting information.',
    form: {
      nameLabel: 'Name',
      emailLabel: 'Email',
      countryLabel: 'Country',
      countryPlaceholder: 'e.g. CN',
      submit: 'Add supplier',
      submitting: 'Adding…',
      genericError: 'Could not create the supplier. Check the fields and try again.'
    },
    table: {
      name: 'Name',
      email: 'Email',
      country: 'Country'
    },
    unknownValue: '—'
  },

  products: {
    pageTitle: 'Products',
    addButton: 'Add product',
    cancelButton: 'Cancel',
    loading: 'Loading…',
    loadError: 'Could not load products.',
    empty: 'No products yet. Add your first one to start tracking packaging data.',
    form: {
      nameLabel: 'Name',
      skuLabel: 'SKU',
      descriptionLabel: 'Description',
      supplierLabel: 'Supplier',
      noSupplierOption: 'No supplier yet',
      submit: 'Add product',
      submitting: 'Adding…',
      genericError: 'Could not create the product. Check the fields and try again.'
    },
    table: {
      name: 'Name',
      sku: 'SKU',
      supplier: 'Supplier',
      packaging: 'Packaging',
      status: 'Status'
    },
    unknownValue: '—'
  },

  productDetail: {
    backLink: '← Back to products',
    skuPrefix: 'SKU:',
    packagingHeading: 'Packaging components',
    addComponentButton: 'Add component',
    cancelButton: 'Cancel',
    loading: 'Loading…',
    empty:
      'No packaging components yet. Add one (box, bag, label, ...) to start tracking this product’s packaging data.',
    notFoundError: 'Could not load this product.',
    form: {
      nameLabel: 'Name',
      namePlaceholder: 'e.g. Outer box',
      packagingTypeLabel: 'Packaging type',
      materialLabel: 'Material',
      materialPlaceholder: 'e.g. cardboard',
      weightLabel: 'Weight (grams)',
      recycledLabel: 'Recycled content (%)',
      submit: 'Add component',
      submitting: 'Adding…',
      genericError: 'Could not add the packaging component. Check the fields and try again.'
    },
    table: {
      name: 'Name',
      type: 'Type',
      material: 'Material',
      weight: 'Weight (g)',
      recycled: 'Recycled %',
      status: 'Status'
    },
    missingFieldsPrefix: 'Missing:',
    unknownValue: '—'
  },

  packagingTypes: {
    box: 'Box',
    bag: 'Bag',
    label: 'Label',
    filler: 'Filler',
    outer_envelope: 'Outer envelope',
    other: 'Other'
  }
};
