'use client'

/**
 * Authentication Context Provider
 * 
 * Provides MSAL authentication context throughout the application.
 * Handles user login, logout, and token acquisition for Fabric Data Agent.
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import { 
  PublicClientApplication, 
  AccountInfo, 
  InteractionRequiredAuthError,
  AuthenticationResult,
  EventType,
  EventMessage,
} from '@azure/msal-browser'
import { 
  msalConfig, 
  loginRequest, 
  fabricTokenRequest, 
  isMsalConfigured,
  FABRIC_SCOPES,
} from './msal-config'

interface AuthContextType {
  /** Whether MSAL is configured (env vars present) */
  isConfigured: boolean
  /** Whether authentication is being initialized */
  isLoading: boolean
  /** Whether user is authenticated */
  isAuthenticated: boolean
  /** Currently signed-in user account */
  account: AccountInfo | null
  /** User's display name */
  userName: string | null
  /** Error message if any */
  error: string | null
  /** Sign in with Azure AD */
  login: () => Promise<void>
  /** Sign out */
  logout: () => Promise<void>
  /** Get access token for Fabric (for passing to backend) */
  getFabricToken: () => Promise<string | null>
  /** Get access token for Azure AI */
  getAzureAIToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Singleton MSAL instance
let msalInstance: PublicClientApplication | null = null

function getMsalInstance(): PublicClientApplication | null {
  if (!isMsalConfigured()) {
    return null
  }
  
  if (!msalInstance && typeof window !== 'undefined') {
    msalInstance = new PublicClientApplication(msalConfig)
  }
  
  return msalInstance
}

interface AuthProviderProps {
  children: React.ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [account, setAccount] = useState<AccountInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  
  const isConfigured = isMsalConfigured()
  const instance = getMsalInstance()

  // Initialize MSAL and check for existing session
  useEffect(() => {
    async function initMsal() {
      if (!instance) {
        setIsLoading(false)
        return
      }

      try {
        // Handle redirect response (if coming back from login)
        await instance.initialize()
        const response = await instance.handleRedirectPromise()
        
        if (response?.account) {
          setAccount(response.account)
          instance.setActiveAccount(response.account)
        } else {
          // Check for existing session
          const accounts = instance.getAllAccounts()
          if (accounts.length > 0) {
            setAccount(accounts[0])
            instance.setActiveAccount(accounts[0])
          }
        }

        // Listen for account changes
        instance.addEventCallback((event: EventMessage) => {
          if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
            const payload = event.payload as AuthenticationResult
            setAccount(payload.account)
            instance.setActiveAccount(payload.account)
          }
          if (event.eventType === EventType.LOGOUT_SUCCESS) {
            setAccount(null)
          }
        })
      } catch (err) {
        console.error('[Auth] MSAL initialization error:', err)
        setError(err instanceof Error ? err.message : 'Authentication initialization failed')
      } finally {
        setIsLoading(false)
      }
    }

    initMsal()
  }, [instance])

  const login = useCallback(async () => {
    if (!instance) {
      setError('Authentication not configured. Please set NEXT_PUBLIC_AZURE_CLIENT_ID and NEXT_PUBLIC_AZURE_TENANT_ID.')
      return
    }

    setError(null)
    try {
      // Use popup for better UX (no full page redirect)
      const response = await instance.loginPopup(loginRequest)
      if (response.account) {
        setAccount(response.account)
        instance.setActiveAccount(response.account)
      }
    } catch (err) {
      console.error('[Auth] Login error:', err)
      setError(err instanceof Error ? err.message : 'Login failed')
    }
  }, [instance])

  const logout = useCallback(async () => {
    if (!instance) return

    try {
      await instance.logoutPopup({
        postLogoutRedirectUri: window.location.origin,
      })
      setAccount(null)
    } catch (err) {
      console.error('[Auth] Logout error:', err)
      setError(err instanceof Error ? err.message : 'Logout failed')
    }
  }, [instance])

  const getFabricToken = useCallback(async (): Promise<string | null> => {
    if (!instance || !account) {
      return null
    }

    try {
      // Try silent token acquisition first
      const response = await instance.acquireTokenSilent({
        ...fabricTokenRequest,
        account,
      })
      return response.accessToken
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        // Fallback to interactive if silent fails
        try {
          const response = await instance.acquireTokenPopup(fabricTokenRequest)
          return response.accessToken
        } catch (popupErr) {
          console.error('[Auth] Token popup error:', popupErr)
          setError('Failed to acquire Fabric token. Please try logging in again.')
          return null
        }
      }
      console.error('[Auth] Token error:', err)
      return null
    }
  }, [instance, account])

  const getAzureAIToken = useCallback(async (): Promise<string | null> => {
    if (!instance || !account) {
      return null
    }

    try {
      // Try silent token acquisition for Azure AI scope
      const response = await instance.acquireTokenSilent({
        scopes: ['https://ai.azure.com/.default'],
        account,
      })
      return response.accessToken
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        try {
          const response = await instance.acquireTokenPopup({
            scopes: ['https://ai.azure.com/.default'],
          })
          return response.accessToken
        } catch (popupErr) {
          console.error('[Auth] Azure AI token popup error:', popupErr)
          return null
        }
      }
      console.error('[Auth] Azure AI token error:', err)
      return null
    }
  }, [instance, account])

  const value = useMemo(() => ({
    isConfigured,
    isLoading,
    isAuthenticated: !!account,
    account,
    userName: account?.name || account?.username || null,
    error,
    login,
    logout,
    getFabricToken,
    getAzureAIToken,
  }), [isConfigured, isLoading, account, error, login, logout, getFabricToken, getAzureAIToken])

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Hook to access authentication context
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

/**
 * Hook to get a function that returns the current Fabric token
 * Useful for making authenticated API calls
 */
export function useFabricToken() {
  const { getFabricToken, isAuthenticated } = useAuth()
  
  return useCallback(async () => {
    if (!isAuthenticated) return null
    return getFabricToken()
  }, [getFabricToken, isAuthenticated])
}
