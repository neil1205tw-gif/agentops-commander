export type Role = 'viewer' | 'operator' | 'admin'

export interface AuthUser {
  id: string
  email: string | null
  display_name: string | null
  role: Role
}

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'
