# Frontend Sub-project

This is the frontend application for the Cogitate project, built with React, TypeScript, and Vite.

**Quick Links**:
- [Root README](../README.md) - setup, the service layout and the documentation index

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Development](#development)
- [Building for Production](#building-for-production)
- [Configuration Files](#configuration-files)
- [Logging](#logging)
- [Project Structure](#project-structure)

## Prerequisites

- Node.js (version 18 or higher)
- npm (comes with Node.js)

## Installation

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

## Development

### Starting the Development Server

To start the development server with hot module replacement:

```bash
npm run dev
```

The application will be available at `http://localhost:5173` by default.

### Stopping the Development Server

To stop the development server, press `Ctrl+C` in the terminal where the server is running.

### Linting

To check for linting issues:

```bash
npm run lint
```

To fix auto-fixable linting issues:

```bash
npm run lint -- --fix
```

## Building for Production

To create a production build:

```bash
npm run build
```

The built files will be output to the `dist` directory.

### Previewing the Production Build

To preview the production build locally:

```bash
npm run preview
```

## Configuration Files

The frontend application uses several configuration files:

- **[vite.config.ts](vite.config.ts#L5-L7)** - Vite configuration
- **[tsconfig.json](tsconfig.json)** - Base TypeScript configuration
- **[tsconfig.app.json](tsconfig.app.json)** - TypeScript configuration for the application
- **[tsconfig.node.json](tsconfig.node.json)** - TypeScript configuration for Node.js environment
- **[src/index.css](src/index.css)** - Global CSS styles and Tailwind CSS configuration

## Environment Variables

### API URL Configuration

The frontend application uses environment variables to configure flexible API URLs for backend communication. The primary environment variable is `VITE_API_URL`, which defines the base URL of the backend API server. This allows developers to switch between development, staging, and production environments without modifying the source code.

During development, Vite automatically loads environment variables from `.env` files. Variables prefixed with `VITE_` are exposed to the client-side JavaScript code and can be accessed via `import.meta.env.VITE_API_URL`. This variable is used in API client configurations, such as Axios instances or fetch calls, to construct endpoints for data retrieval, submissions, and other backend interactions.

For example, in components or hooks that make API requests (e.g., fetching dashboard data or logs), the base URL is dynamically set based on this variable, ensuring seamless integration with different backend deployments.

#### Setting Environment Variables

1. **Development Environment**:
   - Create or edit the `.env` file in the `frontend` directory.
   - Add the following line:

     ```
     VITE_API_URL=http://localhost:8000
     ```

   - This points to a local backend server running on port 8000. Restart the development server (`npm run dev`) after changes for them to take effect.

2. **Production Environment**:
   - Create or edit the `.env.production` file in the `frontend` directory.
   - Add the following line:

     ```
     VITE_API_URL=https://api.yourdomain.com
     ```

   - Replace `https://api.yourdomain.com` with your actual production API endpoint. When building for production (`npm run build`), Vite will use this file.

**Note**: Never commit sensitive environment variables (e.g., API keys) to version control. Use `.env.example` as a template for team members. If additional variables are needed in the future, follow the same `VITE_` prefix convention for client-side exposure.

## Backend CORS Configuration

The backend's CORS (Cross-Origin Resource Sharing) configuration has been updated to support requests from the Dockerized frontend. This allows the frontend running in a Docker container to communicate with the backend API without CORS policy violations.

### Key Update

- Added the Docker frontend origin (e.g., `http://localhost:3000`) to the list of allowed origins in the FastAPI CORS middleware.

This change ensures seamless integration between the Dockerized frontend and the backend during development and deployment.

### Configuring CORS for the Backend

To configure CORS in the FastAPI backend, use the `CORSMiddleware` in your main application file. Here's an example:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local development
        "http://localhost:3000",  # Docker frontend
        "https://your-production-domain.com",  # Production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Your routes here
```

**Notes:**
- Adjust the `allow_origins` list based on your environment.
- For security, avoid using `["*"]` for `allow_origins` in production; specify exact domains instead.
- The `allow_methods` should include methods used by your API.

For more details, refer to the [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/).
## Logging

This frontend application is a client-side React application that runs in the browser. It doesn't write to traditional log files on the server. Instead, it:

1. Displays logs in the browser's developer console
2. Has a dedicated [Logs page](src/pages/Logs.tsx) that shows system events and messages

For debugging purposes, you can:
- Open the browser's developer tools (F12) and check the Console tab
- Visit the Logs page in the application to view system events

In a production environment, client-side errors can be captured and sent to a logging service, but this requires additional backend infrastructure.

## Project Structure

```
frontend/
├── src/
│   ├── assets/          # Static assets
│   ├── components/      # Reusable components
│   │   ├── forms/       # Form components
│   │   ├── layout/      # Layout components
│   │   └── ui/          # UI components
│   ├── hooks/           # Custom React hooks
│   ├── pages/           # Page components
│   ├── utils/           # Utility functions
│   ├── App.css          # App-specific styles
│   ├── App.tsx          # Main App component
│   ├── index.css        # Global styles
│   └── main.tsx         # Application entry point
├── public/              # Public assets
├── index.html           # Main HTML file
├── package.json         # Project dependencies and scripts
├── vite.config.ts       # Vite configuration
├── postcss.config.js    # PostCSS configuration
├── tsconfig.json        # Base TypeScript configuration
├── tsconfig.app.json    # TypeScript configuration for app
├── tsconfig.node.json   # TypeScript configuration for Node
└── README.md            # This file
