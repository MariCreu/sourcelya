import { PackagingType } from '../../services/packaging-component.models';

export interface Dictionary {
  nav: {
    dashboard: string;
    suppliers: string;
    products: string;
    logout: string;
  };

  statusLabels: {
    green: string;
    orange: string;
    red: string;
  };

  auth: {
    login: {
      title: string;
      emailLabel: string;
      passwordLabel: string;
      submit: string;
      submitting: string;
      switchPrompt: string;
      switchLink: string;
      genericError: string;
    };
    signup: {
      title: string;
      emailLabel: string;
      passwordLabel: string;
      submit: string;
      submitting: string;
      switchPrompt: string;
      switchLink: string;
      genericError: string;
      confirmationTitle: string;
      confirmationBody: (email: string) => string;
      goToLogin: string;
    };
  };

  onboarding: {
    title: string;
    subtitle: string;
    companyNameLabel: string;
    countryLabel: string;
    countryPlaceholder: string;
    submit: string;
    submitting: string;
    genericError: string;
    loadError: string;
  };

  suppliers: {
    pageTitle: string;
    addButton: string;
    cancelButton: string;
    loading: string;
    loadError: string;
    empty: string;
    form: {
      nameLabel: string;
      emailLabel: string;
      countryLabel: string;
      countryPlaceholder: string;
      submit: string;
      submitting: string;
      genericError: string;
    };
    table: {
      name: string;
      email: string;
      country: string;
    };
    unknownValue: string;
  };

  products: {
    pageTitle: string;
    addButton: string;
    cancelButton: string;
    loading: string;
    loadError: string;
    empty: string;
    form: {
      nameLabel: string;
      skuLabel: string;
      descriptionLabel: string;
      supplierLabel: string;
      noSupplierOption: string;
      submit: string;
      submitting: string;
      genericError: string;
    };
    table: {
      name: string;
      sku: string;
      supplier: string;
      packaging: string;
      status: string;
    };
    unknownValue: string;
  };

  productDetail: {
    backLink: string;
    skuPrefix: string;
    packagingHeading: string;
    addComponentButton: string;
    cancelButton: string;
    loading: string;
    empty: string;
    notFoundError: string;
    form: {
      nameLabel: string;
      namePlaceholder: string;
      packagingTypeLabel: string;
      materialLabel: string;
      materialPlaceholder: string;
      weightLabel: string;
      recycledLabel: string;
      submit: string;
      submitting: string;
      genericError: string;
    };
    table: {
      name: string;
      type: string;
      material: string;
      weight: string;
      recycled: string;
      status: string;
    };
    missingFieldsPrefix: string;
    unknownValue: string;
  };

  packagingTypes: Record<PackagingType, string>;
}
