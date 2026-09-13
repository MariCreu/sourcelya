import { Dictionary } from './types';

export const en: Dictionary = {
  nav: {
    dashboard: 'Dashboard',
    suppliers: 'Suppliers',
    products: 'Products',
    requests: 'Requests',
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
  },

  requestStatusLabels: {
    draft: 'Draft',
    sent: 'Sent',
    opened: 'Opened by supplier',
    in_progress: 'In progress',
    submitted: 'Submitted by supplier',
    missing_information: 'Missing information',
    review_required: 'Review required',
    conflict: 'Conflict',
    completed: 'Complete'
  },

  requests: {
    pageTitle: 'Requests',
    newButton: 'New request',
    loading: 'Loading…',
    loadError: 'Could not load requests.',
    empty: 'No requests sent yet. Create the first one to ask a supplier for information.',
    table: {
      supplier: 'Supplier',
      products: 'Products',
      language: 'Language',
      status: 'Status',
      sentAt: 'Sent',
      lastActivity: 'Last activity'
    },
    unknownValue: '—',
    languageLabels: { es: 'Spanish', en: 'English' },
    new: {
      backLink: '← Back to requests',
      title: 'New request',
      supplierLabel: 'Supplier',
      chooseSupplierOption: 'Choose a supplier',
      productsLabel: 'Products to request',
      noProductsForSupplier: 'This supplier has no products yet.',
      languageLabel: 'Request language',
      submit: 'Create request',
      submitting: 'Creating…',
      genericError: 'Could not create the request. Check the fields and try again.',
      needsAtLeastOneProduct: 'Select at least one product.'
    },
    detail: {
      backLink: '← Back to requests',
      statusLabel: 'Status',
      timelineHeading: 'Activity',
      timeline: {
        created: 'Created',
        sent: 'Sent',
        opened: 'Opened by supplier',
        submitted: 'Completed by supplier'
      },
      productsHeading: 'Included products',
      sendButton: 'Send request',
      sending: 'Sending…',
      revokeButton: 'Revoke link',
      revoking: 'Revoking…',
      resendButton: 'Resend email',
      resending: 'Resending…',
      confirmRevoke: 'Revoke this link? The supplier will no longer be able to use it.',
      linkRevealedTitle: 'Secure link generated',
      linkRevealedBody:
        "It's been emailed to the supplier. For security, this link is only shown once:",
      copyLinkButton: 'Copy link',
      copiedLabel: 'Copied!',
      noActiveLink: 'No link has been sent to this supplier yet.',
      notFoundError: 'Could not load this request.',
      actionError: 'Could not complete that action. Please try again.',
      documentsHeading: 'Documents received',
      noDocuments: 'The supplier has not attached any documents yet.',
      downloadButton: 'Download',
      documentsTable: {
        filename: 'File',
        size: 'Size',
        uploadedAt: 'Uploaded',
        type: 'Type',
        status: 'Processing',
        fields: 'Fields'
      },
      documentTypeLabels: {
        packaging_specification: 'Packaging specification',
        technical_datasheet: 'Technical datasheet',
        certificate: 'Certificate',
        declaration: 'Declaration',
        invoice_commercial: 'Invoice / commercial document',
        other: 'Other'
      },
      extractionStatusLabels: {
        pending: 'Pending',
        processing: 'Processing…',
        completed: 'Completed',
        failed: 'Failed',
        review_required: 'Review required'
      },
      viewFieldsButton: 'View extracted information',
      hideFieldsButton: 'Hide',
      retryButton: 'Retry',
      retrying: 'Retrying…',
      processingErrorPrefix: 'Error:',
      extractedInformationHeading: 'Extracted information',
      noExtractedFields: 'No data was found in this document.',
      fieldLabels: {
        packaging_type: 'Packaging type',
        material: 'Material',
        weight_grams: 'Weight (g)',
        recycled_content_percentage: 'Recycled content (%)',
        packaging_reference: 'Packaging reference'
      },
      confidenceLabels: {
        high: 'High confidence',
        medium: 'Medium confidence',
        low: 'Low confidence'
      },
      sourcePrefix: 'Source:',
      pagePrefix: 'Page',
      unverifiedEvidence: '(quote not automatically verified)',
      acceptButton: 'Accept',
      rejectButton: 'Reject',
      accepting: 'Accepting…',
      rejecting: 'Rejecting…',
      reviewedLabel: 'Reviewed',
      conflictTitle: 'POSSIBLE CONFLICT',
      conflictCurrentLabel: 'Current value:',
      conflictExtractedLabel: 'Extracted value:',
      useExtractedButton: 'Use extracted value',
      keepCurrentButton: 'Keep current value',
      informationStatusHeading: 'Information status',
      fieldsAvailable: (available: number, total: number) =>
        `${available} / ${total} requested fields available`,
      availableHeading: 'Available',
      missingHeading: 'Missing',
      reviewRequiredHeading: 'Review required',
      conflictHeading: 'Conflict',
      noneLabel: 'None',
      unresolvedPendingMessage: (n: number) =>
        `${n} extraction(s) need you to specify which component they belong to before continuing`,
      requestMissingInfoButton: 'Request missing information',
      requestingFollowUp: 'Sending…',
      followUpSentMessage: 'The missing-information request has been sent.',
      followUpBlockedNothingMissing: 'Nothing is missing for this request.',
      followUpBlockedProcessing: 'Wait for a document to finish processing.',
      followUpBlockedReviewRequired:
        'Resolve the pending extractions or conflicts before requesting more information.',
      followUpBlockedDuplicate: 'This exact information was already requested.',
      followUpBlockedNotEligible: 'This request cannot be followed up on right now.',
      automaticFollowUpLabel: 'Automatic follow-up',
      automaticFollowUpHint:
        'When enabled, Sourcelya automatically requests missing information once there are no pending conflicts or reviews (capped at 3 automatic rounds).',
      followUpRoundsHeading: 'Follow-up history',
      roundLabel: (n: number) => `Round ${n}`,
      roundTriggerManual: 'manual',
      roundTriggerAutomatic: 'automatic',
      roundFieldCount: (n: number) => `${n} field(s) requested`,
      recoveryHeading: 'Information recovery rate',
      recoveryText: (available: number, total: number, rate: number) =>
        `${available} / ${total} fields available (${Math.round(rate * 100)}%)`,
      recoveryFollowUpText: (recovered: number) =>
        `${recovered} additional field(s) recovered through follow-up`
    }
  },

  publicRequest: {
    invalidToken: 'This link is not valid.',
    expiredToken: 'This link has expired. Ask the company to resend the request.',
    revokedToken: 'This link is no longer available.',
    genericError: 'Could not load the request.',
    loading: 'Loading…',
    heading: (companyName: string) => `Information request from ${companyName}`,
    subheading:
      "No account is required. Fill in what packaging data you can and save your progress — you can come back later with this same link.",
    productsHeading: 'Products',
    fields: {
      material: 'Material',
      weightGrams: 'Weight (grams)',
      recycledContentPercentage: 'Recycled content (%)',
      packagingReference: 'Packaging reference',
      notes: 'Notes'
    },
    saveButton: 'Save',
    saving: 'Saving…',
    saveSuccess: 'Progress saved.',
    submitButton: 'Submit request',
    submitting: 'Submitting…',
    submitConfirm: 'Submit this request? You can still view it afterwards, but not edit it.',
    alreadySubmittedTitle: 'Request submitted',
    alreadySubmittedBody: 'Thank you. This request has already been submitted to the company.',
    almostThereTitle: 'Almost there',
    almostThereBody: "Thanks for the information you've already provided. We only need:",
    almostThereFieldLabels: {
      packaging_type: 'Packaging type',
      material: 'Material',
      weight_grams: 'Weight',
      recycled_content_percentage: 'Recycled content',
      packaging_reference: 'Packaging reference'
    },
    poweredBy: 'Managed with Sourcelya',
    documentsHeading: 'Documents',
    documentsHint:
      'Attach technical datasheets, declarations, or other relevant documentation (PDF, XLSX, CSV, DOCX, PNG, JPG).',
    noDocuments: 'You have not attached any documents yet.',
    uploadButton: 'Attach document',
    uploading: 'Uploading…',
    deleteButton: 'Delete',
    deleting: 'Deleting…',
    confirmDelete: 'Delete this document?',
    uploadErrorUnsupportedType: 'That file type is not accepted.',
    uploadErrorTooLarge: 'The file exceeds the maximum allowed size.'
  }
};
