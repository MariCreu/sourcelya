import { PackagingType } from '../../services/packaging-component.models';

export interface Dictionary {
  nav: {
    dashboard: string;
    suppliers: string;
    products: string;
    requests: string;
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

  requestStatusLabels: Record<string, string>;

  requests: {
    pageTitle: string;
    newButton: string;
    loading: string;
    loadError: string;
    empty: string;
    table: {
      supplier: string;
      products: string;
      language: string;
      status: string;
      sentAt: string;
      lastActivity: string;
    };
    unknownValue: string;
    languageLabels: { es: string; en: string };
    new: {
      backLink: string;
      title: string;
      supplierLabel: string;
      chooseSupplierOption: string;
      productsLabel: string;
      noProductsForSupplier: string;
      languageLabel: string;
      submit: string;
      submitting: string;
      genericError: string;
      needsAtLeastOneProduct: string;
    };
    detail: {
      backLink: string;
      statusLabel: string;
      timelineHeading: string;
      timeline: {
        created: string;
        sent: string;
        opened: string;
        submitted: string;
      };
      productsHeading: string;
      sendButton: string;
      sending: string;
      revokeButton: string;
      revoking: string;
      resendButton: string;
      resending: string;
      confirmRevoke: string;
      linkRevealedTitle: string;
      linkRevealedBody: string;
      copyLinkButton: string;
      copiedLabel: string;
      noActiveLink: string;
      notFoundError: string;
      actionError: string;
      documentsHeading: string;
      noDocuments: string;
      downloadButton: string;
      documentsTable: {
        filename: string;
        size: string;
        uploadedAt: string;
        type: string;
        status: string;
        fields: string;
      };
      documentTypeLabels: Record<string, string>;
      extractionStatusLabels: Record<string, string>;
      viewFieldsButton: string;
      hideFieldsButton: string;
      retryButton: string;
      retrying: string;
      processingErrorPrefix: string;
      extractedInformationHeading: string;
      noExtractedFields: string;
      fieldLabels: Record<string, string>;
      confidenceLabels: Record<string, string>;
      sourcePrefix: string;
      pagePrefix: string;
      unverifiedEvidence: string;
      acceptButton: string;
      rejectButton: string;
      accepting: string;
      rejecting: string;
      reviewedLabel: string;
      conflictTitle: string;
      conflictCurrentLabel: string;
      conflictExtractedLabel: string;
      useExtractedButton: string;
      keepCurrentButton: string;
      informationStatusHeading: string;
      fieldsAvailable: (available: number, total: number) => string;
      availableHeading: string;
      missingHeading: string;
      reviewRequiredHeading: string;
      conflictHeading: string;
      noneLabel: string;
      unresolvedPendingMessage: (n: number) => string;
      requestMissingInfoButton: string;
      requestingFollowUp: string;
      followUpSentMessage: string;
      followUpBlockedNothingMissing: string;
      followUpBlockedProcessing: string;
      followUpBlockedReviewRequired: string;
      followUpBlockedDuplicate: string;
      followUpBlockedNotEligible: string;
      automaticFollowUpLabel: string;
      automaticFollowUpHint: string;
      followUpRoundsHeading: string;
      roundLabel: (n: number) => string;
      roundTriggerManual: string;
      roundTriggerAutomatic: string;
      roundFieldCount: (n: number) => string;
      recoveryHeading: string;
      recoveryText: (available: number, total: number, rate: number) => string;
      recoveryFollowUpText: (recovered: number) => string;
    };
  };

  publicRequest: {
    invalidToken: string;
    expiredToken: string;
    revokedToken: string;
    genericError: string;
    loading: string;
    heading: (companyName: string) => string;
    subheading: string;
    productsHeading: string;
    fields: {
      material: string;
      weightGrams: string;
      recycledContentPercentage: string;
      packagingReference: string;
      notes: string;
    };
    saveButton: string;
    saving: string;
    saveSuccess: string;
    submitButton: string;
    submitting: string;
    submitConfirm: string;
    alreadySubmittedTitle: string;
    alreadySubmittedBody: string;
    almostThereTitle: string;
    almostThereBody: string;
    almostThereFieldLabels: Record<string, string>;
    poweredBy: string;
    documentsHeading: string;
    documentsHint: string;
    noDocuments: string;
    uploadButton: string;
    uploading: string;
    deleteButton: string;
    deleting: string;
    confirmDelete: string;
    uploadErrorUnsupportedType: string;
    uploadErrorTooLarge: string;
  };
}
