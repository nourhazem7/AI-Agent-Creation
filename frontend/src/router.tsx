import { createBrowserRouter } from "react-router-dom";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { AgentWizardLayout } from "./components/layout/AgentWizardLayout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import SharedWithMePage from "./pages/SharedWithMePage";
import CreateAgentPage from "./pages/CreateAgentPage";
import ConnectDatabasePage from "./pages/wizard/ConnectDatabasePage";
import KnowledgeAssetsPage from "./pages/wizard/KnowledgeAssetsPage";
import PreparationPage from "./pages/wizard/PreparationPage";
import NotFoundPage from "./pages/NotFoundPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <DashboardPage />
      </ProtectedRoute>
    ),
  },
  {
    path: "/shared",
    element: (
      <ProtectedRoute>
        <SharedWithMePage />
      </ProtectedRoute>
    ),
  },
  {
    path: "/agents/new",
    element: (
      <ProtectedRoute>
        <CreateAgentPage />
      </ProtectedRoute>
    ),
  },
  {
    element: (
      <ProtectedRoute>
        <AgentWizardLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: "/agents/:agentId/connect", element: <ConnectDatabasePage /> },
      { path: "/agents/:agentId/knowledge", element: <KnowledgeAssetsPage /> },
      { path: "/agents/:agentId/preparing", element: <PreparationPage /> },
      // /summary, /validate, /results, /ready land in Milestones 6-9.
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
