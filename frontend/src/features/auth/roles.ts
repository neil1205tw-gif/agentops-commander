import type { Role } from './types'

/** operator 與 admin 可以建立事故。 */
export function canCreateIncident(role: Role): boolean {
  return role === 'operator' || role === 'admin'
}
