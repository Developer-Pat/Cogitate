import React, { lazy } from 'react';
import { Navigate, useParams } from 'react-router-dom';

// Lazy imports for code splitting
const Dashboard = lazy(() => import('../pages/Dashboard'));
const Logs = lazy(() => import('../pages/Logs'));
const Messages = lazy(() => import('../pages/Messages'));
const SystemHistory = lazy(() => import('../pages/SystemHistory'));
const RagIndex = lazy(() => import('../pages/RagIndex'));
const Settings = lazy(() => import('../pages/Settings'));
const AgentIntegration = lazy(() => import('../pages/AgentIntegration'));
const NotFound = lazy(() => import('../pages/NotFound'));
const WorkflowTemplates = lazy(() => import('../pages/WorkflowTemplates'));
const ProviderDashboard = lazy(() => import('../pages/ProviderDashboard'));
const AgentProfiles = lazy(() => import('../pages/AgentProfiles'));
const AgentTemplates = lazy(() => import('../pages/AgentTemplates'));
const Analytics = lazy(() => import('../pages/Analytics'));
const Sessions = lazy(() => import('../pages/Sessions'));
const ProviderModelsBrowser = lazy(() => import('../pages/ProviderModelsBrowser'));
const LocalProviders = lazy(() => import('../pages/LocalProviders'));
const ProviderCapabilities = lazy(() => import('../pages/ProviderCapabilities'));
const ToolManagement = lazy(() => import('../pages/ToolManagement'));
const ComponentGallery = lazy(() => import('../pages/ComponentGallery'));
const CollectionsManagement = lazy(() => import('../pages/CollectionsManagement'));
const CollectionDetail = lazy(() => import('../pages/CollectionDetail'));
const ToolkitsManagement = lazy(() => import('../pages/ToolCollectionsManagement'));
const ToolkitDetail = lazy(() => import('../pages/ToolCollectionDetail'));

// THE LEGACY-PATH REDIRECTS (2026-09-04, the _35 P4 rename): the old
// /toolboxes + /tool-collections routes now point at the /toolkits paths.
const ToolboxPathRedirect = () => {
  const { collectionId } = useParams();
  return React.createElement(Navigate, {
    to: collectionId ? `/toolkits/${collectionId}` : '/toolkits',
    replace: true,
  });
};
const TeamsManagement = lazy(() => import('../pages/TeamsManagement'));
const Macros = lazy(() => import('../pages/Macros'));
const TeamDetail = lazy(() => import('../pages/TeamDetail'));
const CognitivePipeline = lazy(() => import('../pages/CognitivePipeline'));
const LocalServicesPage = lazy(() => import('../pages/LocalServicesPage'));

// Phase 3: Functionality & Testing imports
const Chat = lazy(() => import('../pages/AgentInteraction'));
const ExaChat = lazy(() => import('../pages/ExaChat'));
const WorkflowExecution = lazy(() => import('../pages/WorkflowExecution'));
const TestingDashboard = lazy(() => import('../pages/TestingDashboard'));
const TrashPage = lazy(() => import('../pages/Trash'));
const Debugging = lazy(() => import('../pages/Debugging'));

const WikiViewer = lazy(() => import('../pages/WikiViewer'));
const SetupPage = lazy(() => import('../pages/SetupPage'));

export interface RouteConfig {
  path: string;
  component: React.ComponentType;
  title: string;
  description?: string;
  requiresAuth?: boolean;
  permissions?: string[];
  icon?: string;
  breadcrumb?: string;
  exact?: boolean;
}

export const routes: RouteConfig[] = [
  {
    path: '/',
    component: Dashboard,
    title: 'Dashboard',
    description: 'System overview and quick actions',
    requiresAuth: true,
    icon: 'home',
    breadcrumb: 'Dashboard',
    exact: true
  },
  {
    path: '/setup',
    component: SetupPage,
    title: 'Setup',
    description: 'First-run setup — providers, keys, default model, starter agent',
    requiresAuth: true,
    icon: 'wrench',
    breadcrumb: 'Setup'
  },
  {
    path: '/logs',
    component: Logs,
    title: 'Logs',
    description: 'View and analyze system logs',
    requiresAuth: true,
    icon: 'document-text',
    breadcrumb: 'Logs'
  },
  {
    path: '/history',
    component: SystemHistory,
    title: 'History',
    description: 'Analyze log patterns and message frequencies',
    requiresAuth: true,
    icon: 'chart-bar',
    breadcrumb: 'History'
  },
  {
    path: '/rag-index',
    component: RagIndex,
    title: 'RAG Index',
    description: 'Monitor system health and performance',
    requiresAuth: true,
    icon: 'information-circle',
    breadcrumb: 'System Info'
  },
  {
    path: '/settings',
    component: Settings,
    title: 'Settings',
    description: 'Manage user preferences and application settings',
    requiresAuth: true,
    icon: 'adjustments',
    breadcrumb: 'Settings'
  },
  {
    path: '/macros',
    component: Macros,
    title: 'Macros',
    description: 'Create and manage system macro sets and meta topics',
    requiresAuth: true,
    icon: 'collection',
    breadcrumb: 'Macros'
  },
  {
    path: '/agents/templates',
    component: AgentTemplates,
    title: 'Agent Templates',
    description: 'Browse and use agent templates',
    requiresAuth: true,
    icon: 'template',
    breadcrumb: 'Agent Templates'
  },
  {
    path: '/analytics',
    component: Analytics,
    title: 'Analytics',
    description: 'Usage metrics and performance insights',
    requiresAuth: true,
    icon: 'chart-bar',
    breadcrumb: 'Analytics'
  },
  {
    path: '/sessions',
    component: Sessions,
    title: 'Session Management',
    description: 'Manage and organize your conversation sessions',
    requiresAuth: true,
    icon: 'folder',
    breadcrumb: 'Sessions'
  },
  {
    path: '/messages',
    component: Messages,
    title: 'Message Center',
    description: 'The system message queue — view, filter, and manage the notifications',
    requiresAuth: true,
    icon: 'bell',
    breadcrumb: 'Messages'
  },
  {
    path: '/providers/:providerId/models',
    component: ProviderModelsBrowser,
    title: 'Browse Models',
    description: 'Browse and select provider models',
    requiresAuth: true,
    icon: 'collection',
    breadcrumb: 'Model Browser'
  },
  {
    path: '/workflow-templates',
    component: WorkflowTemplates,
    title: 'Workflows',
    description: 'Configured workflows — each is a template (kind) with concrete parameters',
    requiresAuth: true,
    icon: 'template',
    breadcrumb: 'Workflow Templates'
  },
  {
    path: '/providers',
    component: () => React.createElement(Navigate, { to: '/providers/cloud', replace: true }),
    title: 'Providers',
    description: 'Redirect to Cloud Providers',
    requiresAuth: true,
    icon: 'server',
    breadcrumb: 'Providers'
  },
  {
    path: '/provider-dashboard',
    component: () => React.createElement(Navigate, { to: '/providers/cloud', replace: true }),
    title: 'Provider Dashboard',
    description: 'Redirect to Cloud Providers (the A1 split)',
    requiresAuth: true,
    icon: 'chart-square-bar',
    breadcrumb: 'Provider Dashboard'
  },
  {
    path: '/providers/cloud',
    component: ProviderDashboard,
    title: 'Cloud Providers',
    description: 'The cloud-class provider roof (the A1 split): SaaS providers, usage, health, the curated recommendation layer, and the keys',
    requiresAuth: true,
    icon: 'cloud',
    breadcrumb: 'Cloud Providers'
  },
  {
    path: '/providers/local',
    component: LocalProviders,
    title: 'Local Providers',
    description: 'The local-class provider roof (the A1 split): the daemons, the installed models, and the occupancy',
    requiresAuth: true,
    icon: 'server',
    breadcrumb: 'Local Providers'
  },
  {
    path: '/providers/capabilities',
    component: ProviderCapabilities,
    title: 'Capabilities',
    description: 'What each part of the app uses — the service it resolves to, its backups, and the rung that chose',
    requiresAuth: true,
    icon: 'server',
    breadcrumb: 'Capabilities'
  },
  {
    path: '/agent-interaction',
    component: Chat,
    title: 'Agent Chat',
    description: 'Interact with AI agents using streaming responses',
    requiresAuth: true,
    icon: 'chat-bubble-left-right',
    breadcrumb: 'Chat'
  },
  {
    path: '/exa',
    component: ExaChat,
    title: 'Exa Agent',
    description: 'Chat with Exa — the system agent',
    requiresAuth: true,
    icon: 'chat-bubble-left-right',
    breadcrumb: 'Exa'
  },
  {
    path: '/agent-integration',
    component: AgentIntegration,
    title: 'Exa Config',
    description: 'Configure Exa — the external consulting agent (Hermes/OpenClaw) connection',
    requiresAuth: true,
    icon: 'cpu-chip',
    breadcrumb: 'Exa Agent'
  },
  {
    path: '/workflow-execution',
    component: WorkflowExecution,
    title: 'Workflow Execution',
    description: 'Run a workflow now — select, launch, watch progress',
    requiresAuth: true,
    icon: 'play',
    breadcrumb: 'Workflow Execution'
  },
  {
    path: '/workflow-automation',
    component: WorkflowAutomation,
    title: 'Workflow Automation',
    description: 'Set up recurring workflow runs and monitor their history',
    requiresAuth: true,
    icon: 'refresh',
    breadcrumb: 'Workflow Automation'
  },
  {
    path: '/workflow-products',
    component: WorkflowProducts,
    title: 'Workflow Products',
    description: 'Products delivered by workflow runs — digests, alerts, reports',
    requiresAuth: true,
    icon: 'inbox',
    breadcrumb: 'Workflow Products'
  },
  {
    path: '/products/:path',
    component: ProductViewer,
    title: 'Report',
    description: 'Full-page report viewer',
    requiresAuth: true,
    icon: 'document',
  },
  {
    path: '/testing-dashboard',
    component: TestingDashboard,
    title: 'Testing Dashboard',
    description: 'Comprehensive testing and validation tools',
    requiresAuth: true,
    icon: 'beaker',
    breadcrumb: 'Testing Dashboard'
  },
  {
    path: '/trash',
    component: TrashPage,
    title: 'Trash',
    description: 'Everything moved out of the way rather than erased — five shelves, and the way back off each',
    requiresAuth: true,
    icon: 'trash',
    breadcrumb: 'Trash'
  },
  {
    path: '/components',
    component: ComponentGallery,
    title: 'Gallery',
    description: 'The live control and text vocabulary — every token and role with its sample',
    requiresAuth: true,
    icon: 'layers',
    breadcrumb: 'Gallery'
  },
  {
    path: '/debugging',
    component: Debugging,
    title: 'Debugging',
    description: 'Advanced debugging and troubleshooting tools',
    requiresAuth: true,
    icon: 'bug',
    breadcrumb: 'Debugging'
  },
  {
    path: '/tools',
    component: ToolManagement,
    title: 'Tool Management',
    description: 'Browse, manage, and configure AI agent tools',
    requiresAuth: true,
    icon: 'wrench',
    breadcrumb: 'Tool Management'
  },
  {
    path: '/collections',
    component: CollectionsManagement,
    title: 'Collections',
    description: 'Manage your curated collections of tools, agents, and more',
    requiresAuth: true,
    icon: 'folder',
    breadcrumb: 'Collections'
  },
  {
    path: '/collections/:collectionId',
    component: CollectionDetail,
    title: 'Collection Detail',
    description: 'View and manage collection items',
    requiresAuth: true,
    icon: 'folder-open',
    breadcrumb: 'Collection Detail'
  },
  {
    path: '/toolkits',
    component: ToolkitsManagement,
    title: 'Toolkits',
    description: 'Manage your toolkits — the tool collections an agent owns',
    requiresAuth: true,
    icon: 'folder',
    breadcrumb: 'Toolkits'
  },
  {
    path: '/toolboxes',
    component: () => React.createElement(Navigate, { to: '/toolkits', replace: true }),
    title: 'Toolboxes',
    description: 'Redirect to Toolkits',
    requiresAuth: true,
    icon: 'folder',
    breadcrumb: 'Toolkits'
  },
  {
    path: '/images',
    component: ImageManagement,
    title: 'Image Management',
    description: 'Application image assets — upload, browse, delete, import/export',
    requiresAuth: true,
    icon: 'photo',
    breadcrumb: 'Image Management'
  },
  {
    path: '/skills',
    component: SkillsManagement,
    title: 'Skills Management',
    description: 'Skill assets — browse, curated status, in-use view',
    requiresAuth: true,
    icon: 'sparkles',
    breadcrumb: 'Skills Management'
  },
  {
    path: '/notifications-config',
    component: NotificationsConfigPage,
    title: 'Notifications',
    description: 'The notification-sound config + the mute — the per-class sounds, the level, the volume',
    requiresAuth: false,
    icon: 'bell',
    breadcrumb: 'Notifications'
  },
  {
    path: '/system-configs',
    component: SystemConfigsPage,
    title: 'System Configs',
    description: 'The system status + the config surfaces',
    requiresAuth: true,
    icon: 'server',
    breadcrumb: 'System Configs'
  },
  {
    path: '/speech',
    component: SpeechPage,
    title: 'Speech',
    description: 'The voice (TTS) + the hearing (STT) — the providers, the voices, and the round-trip test facility',
    requiresAuth: false,
    icon: 'mic',
    breadcrumb: 'Speech'
  },
  {
    path: '/local-services',
    component: LocalServicesPage,
    title: 'Local Services',
    description: 'The local services — the local providers (reachability + test) and the capabilities they power (session titles)',
    requiresAuth: false,
    icon: 'server',
    breadcrumb: 'Local Services'
  },
  {
    path: '/sounds',
    component: SoundsManagement,
    title: 'Sounds',
    description: 'Notification-sound assets — upload, browse, preview, pick the toast sound',
    requiresAuth: true,
    icon: 'music',
    breadcrumb: 'Sounds'
  },
  {
    path: '/workflow-kinds',
    component: WorkflowKinds,
    title: 'Templates',
    description: 'The canonical workflow process shapes — a template is a kind',
    requiresAuth: true,
    icon: 'template',
  },
  {
    path: '/toolkits/:collectionId',
    component: ToolkitDetail,
    title: 'Toolkit Detail',
    description: 'View and manage tools in a toolkit',
    requiresAuth: true,
    icon: 'folder-open',
    breadcrumb: 'Toolkit Detail'
  },
  {
    path: '/toolboxes/:collectionId',
    component: ToolboxPathRedirect,
    title: 'Toolboxes',
    description: 'Redirect to the Toolkit',
    requiresAuth: true,
    icon: 'folder-open',
    breadcrumb: 'Toolkit Detail'
  },
  {
    path: '/tool-collections/:collectionId',
    component: ToolboxPathRedirect,
    title: 'Tool Collections',
    description: 'Redirect to the Toolkit',
    requiresAuth: true,
    icon: 'folder-open',
    breadcrumb: 'Toolkit Detail'
  },
  {
    path: '/teams',
    component: TeamsManagement,
    title: 'Collectives',
    description: 'Organize agents into collectives — groups by a common attribute',
    requiresAuth: true,
    icon: 'users',
    breadcrumb: 'Collectives'
  },
  {
    path: '/teams/:teamId',
    component: TeamDetail,
    title: 'Collective Detail',
    description: 'View and manage collective members',
    requiresAuth: true,
    icon: 'user-friends',
    breadcrumb: 'Collective Detail'
  },
  {
    path: '/docs/*',
    component: WikiViewer,
    title: 'Application Atlas',
    description: 'Application Atlas — frontend UI documentation',
    requiresAuth: false,
    icon: 'book-open',
    breadcrumb: 'Application Atlas'
  },
  {
    path: '/cognitive-pipeline',
    component: CognitivePipeline,
    title: 'Cognitive Pipeline',
    description: 'Configure cognitive pipeline strategies, memory profiles, and cognitive profiles for agents',
    requiresAuth: true,
    permissions: ['admin', 'config_manager', 'developer'],
    icon: 'brain',
    breadcrumb: 'Cognitive Pipeline'
  },
  {
    path: '/agent-profiles',
    component: AgentProfiles,
    title: 'Agent Profiles',
    description: 'View and manage agent cognitive profiles',
    requiresAuth: true,
    icon: 'user',
    breadcrumb: 'Agent Profiles'
  },
  {
    path: '/wiki/*',
    component: WikiViewer,
    title: 'Wiki',
    description: 'Project knowledge base — LLM Wiki',
    requiresAuth: false,
    icon: 'book-open',
    breadcrumb: 'Wiki'
  },
  {
    path: '*',
    component: NotFound,
    title: 'Not Found',
    description: 'Page not found',
    requiresAuth: false,
    breadcrumb: '404'
  }
];

// Helper functions for route management
export const getRouteByPath = (path: string): RouteConfig | undefined => {
  return routes.find(route => route.path === path);
};

export const getPublicRoutes = (): RouteConfig[] => {
  return routes.filter(route => !route.requiresAuth);
};

export const getProtectedRoutes = (): RouteConfig[] => {
  return routes.filter(route => route.requiresAuth);
};

export const getNavigationRoutes = (): RouteConfig[] => {
  return routes.filter(route => 
    route.path !== '*' && 
    route.requiresAuth !== false
  );
};

// Route permissions check
export const hasRoutePermission = (route: RouteConfig, userPermissions: string[] = []): boolean => {
  if (!route.permissions || route.permissions.length === 0) {
    return true;
  }
  
  return route.permissions.some(permission => 
    userPermissions.includes(permission)
  );
};

// Breadcrumb generation
export const generateBreadcrumbs = (currentPath: string): Array<{ path: string; title: string }> => {
  const breadcrumbs = [];
  const pathSegments = currentPath.split('/').filter(segment => segment);
  
  let accumulatedPath = '';
  for (const segment of pathSegments) {
    accumulatedPath += `/${segment}`;
    const route = getRouteByPath(accumulatedPath);
    if (route) {
      breadcrumbs.push({
        path: accumulatedPath,
        title: route.breadcrumb || route.title
      });
    }
  }
  
  return breadcrumbs;
};

import WorkflowAutomation from '../pages/WorkflowAutomation';
import WorkflowProducts from '../pages/WorkflowProducts';
import ProductViewer from '../pages/ProductViewer';
export default routes
import ImageManagement from '../pages/ImageManagement';
import SkillsManagement from '../pages/SkillsManagement';
import SoundsManagement from '../pages/SoundsManagement';
import SystemConfigsPage from '../pages/SystemConfigsPage';
import SpeechPage from '../pages/SpeechPage';
import NotificationsConfigPage from '../pages/NotificationsConfigPage';
import WorkflowKinds from '../pages/WorkflowKinds';