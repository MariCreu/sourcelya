import { Dictionary } from './types';

export const es: Dictionary = {
  nav: {
    dashboard: 'Panel',
    suppliers: 'Proveedores',
    products: 'Productos',
    requests: 'Solicitudes',
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
  },

  requestStatusLabels: {
    draft: 'Borrador',
    sent: 'Enviada',
    opened: 'Abierta por el proveedor',
    in_progress: 'En progreso',
    submitted: 'Enviada por el proveedor',
    missing_information: 'Falta información',
    review_required: 'Requiere revisión',
    conflict: 'Conflicto',
    completed: 'Completa'
  },

  requests: {
    pageTitle: 'Solicitudes',
    newButton: 'Nueva solicitud',
    loading: 'Cargando…',
    loadError: 'No se han podido cargar las solicitudes.',
    empty:
      'Todavía no has enviado ninguna solicitud. Crea la primera para pedir información a un proveedor.',
    table: {
      supplier: 'Proveedor',
      products: 'Productos',
      language: 'Idioma',
      status: 'Estado',
      sentAt: 'Enviada',
      lastActivity: 'Última actividad'
    },
    unknownValue: '—',
    languageLabels: { es: 'Español', en: 'Inglés' },
    new: {
      backLink: '← Volver a solicitudes',
      title: 'Nueva solicitud',
      supplierLabel: 'Proveedor',
      chooseSupplierOption: 'Elige un proveedor',
      productsLabel: 'Productos a solicitar',
      noProductsForSupplier: 'Este proveedor todavía no tiene productos.',
      languageLabel: 'Idioma de la solicitud',
      submit: 'Crear solicitud',
      submitting: 'Creando…',
      genericError: 'No se ha podido crear la solicitud. Revisa los campos e inténtalo de nuevo.',
      needsAtLeastOneProduct: 'Selecciona al menos un producto.'
    },
    detail: {
      backLink: '← Volver a solicitudes',
      statusLabel: 'Estado',
      timelineHeading: 'Actividad',
      timeline: {
        created: 'Creada',
        sent: 'Enviada',
        opened: 'Abierta por el proveedor',
        submitted: 'Completada por el proveedor'
      },
      productsHeading: 'Productos incluidos',
      sendButton: 'Enviar solicitud',
      sending: 'Enviando…',
      revokeButton: 'Revocar enlace',
      revoking: 'Revocando…',
      resendButton: 'Reenviar email',
      resending: 'Reenviando…',
      confirmRevoke: '¿Seguro que quieres revocar el enlace? El proveedor ya no podrá usarlo.',
      linkRevealedTitle: 'Enlace seguro generado',
      linkRevealedBody:
        'Se ha enviado por email al proveedor. Por seguridad, este enlace solo se muestra una vez:',
      copyLinkButton: 'Copiar enlace',
      copiedLabel: '¡Copiado!',
      noActiveLink: 'Todavía no se ha enviado ningún enlace a este proveedor.',
      notFoundError: 'No se ha podido cargar esta solicitud.',
      actionError: 'No se ha podido completar la acción. Inténtalo de nuevo.',
      documentsHeading: 'Documentos recibidos',
      noDocuments: 'El proveedor todavía no ha adjuntado ningún documento.',
      downloadButton: 'Descargar',
      documentsTable: {
        filename: 'Archivo',
        size: 'Tamaño',
        uploadedAt: 'Subido',
        type: 'Tipo',
        status: 'Procesamiento',
        fields: 'Campos'
      },
      documentTypeLabels: {
        packaging_specification: 'Especificación de packaging',
        technical_datasheet: 'Ficha técnica',
        certificate: 'Certificado',
        declaration: 'Declaración',
        invoice_commercial: 'Factura / documento comercial',
        other: 'Otro'
      },
      extractionStatusLabels: {
        pending: 'Pendiente',
        processing: 'Procesando…',
        completed: 'Completado',
        failed: 'Error',
        review_required: 'Requiere revisión'
      },
      viewFieldsButton: 'Ver información extraída',
      hideFieldsButton: 'Ocultar',
      retryButton: 'Reintentar',
      retrying: 'Reintentando…',
      processingErrorPrefix: 'Error:',
      extractedInformationHeading: 'Información extraída',
      noExtractedFields: 'No se ha encontrado ningún dato en este documento.',
      fieldLabels: {
        packaging_type: 'Tipo de packaging',
        material: 'Material',
        weight_grams: 'Peso (g)',
        recycled_content_percentage: 'Contenido reciclado (%)',
        packaging_reference: 'Referencia de packaging'
      },
      confidenceLabels: {
        high: 'Alta confianza',
        medium: 'Confianza media',
        low: 'Baja confianza'
      },
      sourcePrefix: 'Fuente:',
      pagePrefix: 'Página',
      unverifiedEvidence: '(cita no verificada automáticamente)',
      acceptButton: 'Aceptar',
      rejectButton: 'Rechazar',
      accepting: 'Aceptando…',
      rejecting: 'Rechazando…',
      reviewedLabel: 'Revisado',
      conflictTitle: 'POSIBLE CONFLICTO',
      conflictCurrentLabel: 'Valor actual:',
      conflictExtractedLabel: 'Valor extraído:',
      useExtractedButton: 'Usar valor extraído',
      keepCurrentButton: 'Mantener valor actual',
      informationStatusHeading: 'Estado de la información',
      fieldsAvailable: (available: number, total: number) =>
        `${available} / ${total} campos solicitados disponibles`,
      availableHeading: 'Disponible',
      missingHeading: 'Falta',
      reviewRequiredHeading: 'Requiere revisión',
      conflictHeading: 'Conflicto',
      noneLabel: 'Ninguno',
      unresolvedPendingMessage: (n: number) =>
        `${n} extracción(es) necesitan que indiques a qué componente pertenecen antes de continuar`,
      requestMissingInfoButton: 'Solicitar información faltante',
      requestingFollowUp: 'Enviando…',
      followUpSentMessage: 'Se ha enviado la solicitud de información faltante.',
      followUpBlockedNothingMissing: 'No falta ninguna información en esta solicitud.',
      followUpBlockedProcessing: 'Espera a que termine de procesarse un documento.',
      followUpBlockedReviewRequired:
        'Resuelve las extracciones pendientes de revisión o los conflictos antes de solicitar más información.',
      followUpBlockedDuplicate: 'Ya se solicitó exactamente esta misma información.',
      followUpBlockedNotEligible: 'Esta solicitud no admite un nuevo seguimiento ahora mismo.',
      automaticFollowUpLabel: 'Seguimiento automático',
      automaticFollowUpHint:
        'Si se activa, Sourcelya solicitará automáticamente la información que falte cuando no haya conflictos ni revisiones pendientes (máximo 3 rondas automáticas).',
      followUpRoundsHeading: 'Historial de seguimiento',
      roundLabel: (n: number) => `Ronda ${n}`,
      roundTriggerManual: 'manual',
      roundTriggerAutomatic: 'automático',
      roundFieldCount: (n: number) => `${n} campo(s) solicitado(s)`,
      recoveryHeading: 'Tasa de recuperación de información',
      recoveryText: (available: number, total: number, rate: number) =>
        `${available} / ${total} campos disponibles (${Math.round(rate * 100)}%)`,
      recoveryFollowUpText: (recovered: number) =>
        `${recovered} campo(s) adicionales recuperados gracias al seguimiento`
    }
  },

  publicRequest: {
    invalidToken: 'Este enlace no es válido.',
    expiredToken: 'Este enlace ha caducado. Pide a la empresa que te reenvíe la solicitud.',
    revokedToken: 'Este enlace ya no está disponible.',
    genericError: 'No se ha podido cargar la solicitud.',
    loading: 'Cargando…',
    heading: (companyName: string) => `Solicitud de información de ${companyName}`,
    subheading:
      'No necesitas crear una cuenta. Completa los datos de packaging que puedas y guarda tu progreso; puedes volver más tarde con el mismo enlace.',
    productsHeading: 'Productos',
    fields: {
      material: 'Material',
      weightGrams: 'Peso (gramos)',
      recycledContentPercentage: 'Contenido reciclado (%)',
      packagingReference: 'Referencia de packaging',
      notes: 'Notas'
    },
    saveButton: 'Guardar',
    saving: 'Guardando…',
    saveSuccess: 'Progreso guardado.',
    submitButton: 'Enviar solicitud',
    submitting: 'Enviando…',
    submitConfirm: '¿Enviar la solicitud? Podrás seguir viéndola, pero no editarla después.',
    alreadySubmittedTitle: 'Solicitud enviada',
    alreadySubmittedBody: 'Gracias. Esta solicitud ya ha sido enviada a la empresa.',
    almostThereTitle: 'Ya casi está',
    almostThereBody: 'Gracias por la información que ya nos has enviado. Solo necesitamos:',
    almostThereFieldLabels: {
      packaging_type: 'Tipo de packaging',
      material: 'Material',
      weight_grams: 'Peso',
      recycled_content_percentage: 'Contenido reciclado',
      packaging_reference: 'Referencia de packaging'
    },
    poweredBy: 'Gestionado con Sourcelya',
    documentsHeading: 'Documentos',
    documentsHint: 'Adjunta fichas técnicas, declaraciones u otra documentación relevante (PDF, XLSX, CSV, DOCX, PNG, JPG).',
    noDocuments: 'Todavía no has adjuntado ningún documento.',
    uploadButton: 'Adjuntar documento',
    uploading: 'Subiendo…',
    deleteButton: 'Eliminar',
    deleting: 'Eliminando…',
    confirmDelete: '¿Eliminar este documento?',
    uploadErrorUnsupportedType: 'Ese tipo de archivo no está permitido.',
    uploadErrorTooLarge: 'El archivo supera el tamaño máximo permitido.'
  }
};
