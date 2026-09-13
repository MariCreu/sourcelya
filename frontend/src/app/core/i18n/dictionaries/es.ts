import { Dictionary } from './types';

export const es: Dictionary = {
  nav: {
    dashboard: 'Panel',
    suppliers: 'Proveedores',
    products: 'Productos',
    logout: 'Cerrar sesión'
  },

  statusLabels: {
    green: 'Completo',
    orange: 'Falta información',
    red: 'Requiere revisión'
  },

  auth: {
    login: {
      title: 'Iniciar sesión',
      emailLabel: 'Email',
      passwordLabel: 'Contraseña',
      submit: 'Iniciar sesión',
      submitting: 'Iniciando sesión…',
      switchPrompt: '¿No tienes cuenta?',
      switchLink: 'Empieza gratis',
      genericError: 'No se ha podido iniciar sesión.'
    },
    signup: {
      title: 'Empieza gratis',
      emailLabel: 'Email',
      passwordLabel: 'Contraseña',
      submit: 'Crear cuenta',
      submitting: 'Creando cuenta…',
      switchPrompt: '¿Ya tienes cuenta?',
      switchLink: 'Iniciar sesión',
      genericError: 'No se ha podido crear la cuenta.',
      confirmationTitle: 'Revisa tu email',
      confirmationBody: (email: string) =>
        `Te hemos enviado un enlace de confirmación a ${email}. Confírmalo y después inicia sesión para configurar Sourcelya.`,
      goToLogin: 'Ir a iniciar sesión'
    }
  },

  onboarding: {
    title: 'Configura tu empresa',
    subtitle: 'Un último paso antes de poder invitar a proveedores.',
    companyNameLabel: 'Nombre de la empresa',
    countryLabel: 'País',
    countryPlaceholder: 'ej. ES',
    submit: 'Crear empresa',
    submitting: 'Creando…',
    genericError: 'No se ha podido crear la empresa. Revisa los campos e inténtalo de nuevo.',
    loadError: 'No se ha podido cargar tu cuenta.'
  },

  suppliers: {
    pageTitle: 'Proveedores',
    addButton: 'Añadir proveedor',
    cancelButton: 'Cancelar',
    loading: 'Cargando…',
    loadError: 'No se han podido cargar los proveedores.',
    empty: 'Todavía no tienes proveedores. Añade el primero para empezar a solicitar información.',
    form: {
      nameLabel: 'Nombre',
      emailLabel: 'Email',
      countryLabel: 'País',
      countryPlaceholder: 'ej. CN',
      submit: 'Añadir proveedor',
      submitting: 'Añadiendo…',
      genericError: 'No se ha podido crear el proveedor. Revisa los campos e inténtalo de nuevo.'
    },
    table: {
      name: 'Nombre',
      email: 'Email',
      country: 'País'
    },
    unknownValue: '—'
  },

  products: {
    pageTitle: 'Productos',
    addButton: 'Añadir producto',
    cancelButton: 'Cancelar',
    loading: 'Cargando…',
    loadError: 'No se han podido cargar los productos.',
    empty: 'Todavía no tienes productos. Añade el primero para empezar a controlar su packaging.',
    form: {
      nameLabel: 'Nombre',
      skuLabel: 'SKU',
      descriptionLabel: 'Descripción',
      supplierLabel: 'Proveedor',
      noSupplierOption: 'Sin proveedor todavía',
      submit: 'Añadir producto',
      submitting: 'Añadiendo…',
      genericError: 'No se ha podido crear el producto. Revisa los campos e inténtalo de nuevo.'
    },
    table: {
      name: 'Nombre',
      sku: 'SKU',
      supplier: 'Proveedor',
      packaging: 'Packaging',
      status: 'Estado'
    },
    unknownValue: '—'
  },

  productDetail: {
    backLink: '← Volver a productos',
    skuPrefix: 'SKU:',
    packagingHeading: 'Componentes de packaging',
    addComponentButton: 'Añadir componente',
    cancelButton: 'Cancelar',
    loading: 'Cargando…',
    empty:
      'Todavía no hay componentes de packaging. Añade uno (caja, bolsa, etiqueta...) para empezar a registrar sus datos.',
    notFoundError: 'No se ha podido cargar este producto.',
    form: {
      nameLabel: 'Nombre',
      namePlaceholder: 'ej. Caja exterior',
      packagingTypeLabel: 'Tipo de packaging',
      materialLabel: 'Material',
      materialPlaceholder: 'ej. cartón',
      weightLabel: 'Peso (gramos)',
      recycledLabel: 'Contenido reciclado (%)',
      submit: 'Añadir componente',
      submitting: 'Añadiendo…',
      genericError: 'No se ha podido añadir el componente. Revisa los campos e inténtalo de nuevo.'
    },
    table: {
      name: 'Nombre',
      type: 'Tipo',
      material: 'Material',
      weight: 'Peso (g)',
      recycled: 'Reciclado %',
      status: 'Estado'
    },
    missingFieldsPrefix: 'Falta:',
    unknownValue: '—'
  },

  packagingTypes: {
    box: 'Caja',
    bag: 'Bolsa',
    label: 'Etiqueta',
    filler: 'Relleno',
    outer_envelope: 'Sobre exterior',
    other: 'Otro'
  }
};
