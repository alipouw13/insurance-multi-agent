/**
 * MSAL Configuration for Azure AD Authentication
 * 
 * This module configures Microsoft Authentication Library (MSAL) for
 * authenticating users with Azure AD. The user's token is passed to
 * the backend to enable identity passthrough for Fabric Data Agent.
 */

import { Configuration, LogLevel } from '@azure/msal-browser'

// Scopes required for Fabric Data Agent access
// The Azure AI Foundry scope allows the backend to call Azure AI services on behalf of the user
export const FABRIC_SCOPES = [
  'https://ai.azure.com/.default',  // Azure AI Foundry scope
  'https://api.fabric.microsoft.com/Item.Read.All',  // Fabric read scope
  'https://api.fabric.microsoft.com/Item.Execute.All',  // Fabric execute scope
]

// Default scopes for general authentication
export const LOGIN_SCOPES = ['openid', 'profile', 'email', 'offline_access']

/**
 * MSAL Configuration
 * 
 * Environment Variables:
 * - NEXT_PUBLIC_AZURE_CLIENT_ID: App registration client ID
 * - NEXT_PUBLIC_AZURE_TENANT_ID: Azure AD tenant ID
 * - NEXT_PUBLIC_AZURE_REDIRECT_URI: OAuth redirect URI (defaults to current origin)
 */
export const msalConfig: Configuration = {
  auth: {
    clientId: process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || '',
    authority: `https://login.microsoftonline.com/${process.env.NEXT_PUBLIC_AZURE_TENANT_ID || 'common'}`,
    redirectUri: typeof window !== 'undefined' 
      ? (process.env.NEXT_PUBLIC_AZURE_REDIRECT_URI || window.location.origin)
      : '',
    postLogoutRedirectUri: typeof window !== 'undefined' ? window.location.origin : '',
    navigateToLoginRequestUrl: true,
  },
  cache: {
    cacheLocation: 'localStorage', // Use localStorage for persistence across tabs
    storeAuthStateInCookie: false, // Set to true for IE11/Edge support
  },
  system: {
    loggerOptions: {
      logLevel: process.env.NODE_ENV === 'development' ? LogLevel.Verbose : LogLevel.Warning,
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return
        switch (level) {
          case LogLevel.Error:
            console.error('[MSAL]', message)
            break
          case LogLevel.Warning:
            console.warn('[MSAL]', message)
            break
          case LogLevel.Info:
            console.info('[MSAL]', message)
            break
          case LogLevel.Verbose:
            console.debug('[MSAL]', message)
            break
        }
      },
      piiLoggingEnabled: false,
    },
  },
}

/**
 * Check if MSAL is properly configured
 */
export function isMsalConfigured(): boolean {
  return !!(
    process.env.NEXT_PUBLIC_AZURE_CLIENT_ID && 
    process.env.NEXT_PUBLIC_AZURE_TENANT_ID
  )
}

/**
 * Login request configuration
 */
export const loginRequest = {
  scopes: LOGIN_SCOPES,
}

/**
 * Fabric token request configuration
 * Used to acquire tokens for Fabric Data Agent access
 */
export const fabricTokenRequest = {
  scopes: FABRIC_SCOPES,
}
