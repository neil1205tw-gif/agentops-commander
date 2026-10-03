import type { RouteObject } from 'react-router'

import { RequireAuth } from '../features/auth'
import { IncidentDetailPage } from '../pages/IncidentDetailPage'
import { IncidentsPage } from '../pages/IncidentsPage'
import { LandingPage } from '../pages/LandingPage'
import { LoginPage } from '../pages/LoginPage'
import { NewIncidentPage } from '../pages/NewIncidentPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { Layout } from './Layout'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <LandingPage /> },
      { path: '/login', element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: '/incidents', element: <IncidentsPage /> },
          { path: '/incidents/new', element: <NewIncidentPage /> },
          { path: '/incidents/:id', element: <IncidentDetailPage /> },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
