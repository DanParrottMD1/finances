# Frontend Tutorial 1: set up React, TypeScript, and the API connection

The backend can now create, read, update, delete, filter, and paginate finance
data. In this tutorial you will create the browser application that will use
those endpoints.

The visible result is deliberately small: a page that asks the Flask health
endpoint whether the API and database are available. The important result is
the plumbing underneath it. Later tutorials will build features on the same
React application and API helper.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Understand the frontend tools | 10 minutes |
| Scaffold the project | 10 minutes |
| Trace how React reaches the browser | 10 minutes |
| Add the API helper and health check | 20 minutes |
| Check errors and make a production build | 10 minutes |

## What we are building

During development, two processes will run at the same time:

```text
Browser
  |
  | opens the page
  v
React development server     http://localhost:5173
  |
  | GET /api/health
  v
Flask API                    http://127.0.0.1:5001
  |
  v
MariaDB
```

The page will show one of three states:

```text
Checking API connection...
API and database connected.
Cannot connect: <error message>
```

This small request proves that React is running, the API address is configured,
the browser is allowed through CORS, Flask is running, and Flask can reach the
database.

## Before you start

Complete Backend Tutorial 5 and make sure its tests pass. You will also need
Node.js and npm. Current Vite versions require a current supported Node.js
release; if Vite reports that your version is too old, update Node before
continuing.

Check the tools from the repository root:

```sh
cd ~/finance-app
node --version
npm --version
```

Create a branch for the milestone:

```sh
git switch -c add-frontend-foundation
```

Do not place secrets in frontend environment variables. Anything whose name
starts with `VITE_` is included in browser code and can be read by a user. The
API address is safe to expose; a database password is not.

## Part 1: understand the tools

The names in “React with TypeScript using Vite” have separate jobs:

- **React** describes the interface as components and updates the page when
  component state changes.
- **TypeScript** checks the shapes of values before the browser runs the code.
- **Vite** starts the development server and builds deployable browser files.
- **npm** installs JavaScript packages and runs project scripts.

The Flask API remains responsible for data, validation, and database access.
React must never connect directly to MariaDB.

## Part 2: scaffold the frontend

From the repository root, ask Vite to create its React and TypeScript template:

```sh
cd ~/finance-app
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

The two `--` characters before `--template` tell npm to pass the remaining
option to Vite. The command creates `frontend/package.json`; `npm install` then
downloads the versions recorded there and writes `package-lock.json`.

Start the development server:

```sh
npm run dev
```

Open `http://localhost:5173`. You should see Vite's starter page. Leave this
terminal running. Vite will refresh the page as files change.

The important generated files are:

```text
frontend/
  index.html              browser entry document
  package.json            dependencies and npm scripts
  package-lock.json       exact installed dependency tree
  tsconfig.json           TypeScript project settings
  vite.config.ts          Vite and React integration
  src/
    main.tsx              JavaScript entry point
    App.tsx               root React component
    App.css                styles belonging to App
    index.css              global styles
```

`node_modules/` contains installed packages. It is large and reproducible from
`package-lock.json`, so the Vite template excludes it from Git.

## Part 3: follow the application entry point

Open `frontend/index.html`. Near the bottom, it loads the TypeScript entry
module:

```html
<script type="module" src="/src/main.tsx"></script>
```

Now open `frontend/src/main.tsx`. The generated file renders `<App />` inside
the HTML element whose ID is `root`:

```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

`<App />` looks like an HTML element, but its capital letter means it is a React
component. A component is a function that returns JSX: markup written inside
TypeScript. The `.tsx` extension means the file may contain both.

`StrictMode` helps reveal unsafe component behaviour during development. It may
run setup and cleanup an extra time in development. That can make two health
requests appear in the browser's Network panel; production does not do this.

## Part 4: replace the starter page with an application shell

Replace `frontend/src/App.tsx` with:

```tsx
import './App.css'

function App() {
  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Personal finance</p>
        <h1>Finance tracker</h1>
        <p>Record income and spending in one place.</p>
      </header>

      <section className="panel" aria-labelledby="connection-heading">
        <h2 id="connection-heading">Backend connection</h2>
        <p>Connection check not started.</p>
      </section>
    </main>
  )
}

export default App
```

JSX mostly resembles HTML, with a few differences:

- `className` supplies a CSS class because `class` is a JavaScript keyword;
- JavaScript expressions can appear inside braces `{...}`;
- one component must return one enclosing element;
- `aria-labelledby` gives the section an accessible name using its heading.

Replace `frontend/src/index.css` with these global defaults:

```css
:root {
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #17202a;
  background: #f4f7f6;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

button,
input,
select {
  font: inherit;
}
```

Replace `frontend/src/App.css` with:

```css
.app-shell {
  width: min(70rem, calc(100% - 2rem));
  margin: 0 auto;
  padding: 3rem 0;
}

.page-header {
  margin-bottom: 2rem;
}

.page-header h1 {
  margin: 0;
  font-size: clamp(2rem, 5vw, 3.5rem);
}

.page-header p:last-child {
  color: #52606d;
}

.eyebrow {
  margin-bottom: 0.5rem;
  color: #087f5b;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.panel {
  padding: 1.5rem;
  border: 1px solid #d9e2e1;
  border-radius: 0.75rem;
  background: #ffffff;
  box-shadow: 0 0.5rem 1.5rem rgb(30 55 50 / 8%);
}

.panel h2 {
  margin-top: 0;
}

.status-success {
  color: #087f5b;
}

.status-error {
  color: #c92a2a;
}
```

The browser should now show the Finance tracker shell. The unused starter logo
files can remain for now; because nothing imports them, they are not included in
the page.

## Part 5: configure the API address

Create `frontend/.env.example`:

```text
VITE_API_BASE_URL=http://127.0.0.1:5001/api
```

Then create your local `frontend/.env` with the same value:

```text
VITE_API_BASE_URL=http://127.0.0.1:5001/api
```

Add this line to the root `.gitignore`:

```text
frontend/.env
```

Commit `.env.example`, but not `.env`. Different developers or deployments can
use different API addresses without changing application code.

Vite reads environment files when its server starts. Restart `npm run dev`
after adding or changing `.env`.

## Part 6: create one API helper

Create `frontend/src/api.ts`:

```ts
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:5001/api'

type ApiErrorResponse = {
  error?: string
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiRequest<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options)

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`

    try {
      const body = (await response.json()) as ApiErrorResponse
      if (body.error) {
        message = body.error
      }
    } catch {
      // Keep the status-based message if the response is not JSON.
    }

    throw new ApiError(message, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
```

There are several new TypeScript ideas here:

- `type ApiErrorResponse` describes JSON that may have an `error` string.
- `RequestInit` is the browser's type for options such as method and headers.
- `Promise<T>` means the eventual result has a type chosen by the caller.
- the generic `<T>` lets this one helper return health data now and transaction
  data later;
- `response.ok` is true for HTTP success statuses from 200 through 299;
- a thrown `ApiError` preserves both the useful message and HTTP status;
- a 204 response has no JSON body, which will matter when deletion is added.

The helper handles transport details, not application state. Components will
decide when to make a request and what the user should see while it runs.

## Part 7: call Flask from a React component

Replace `frontend/src/App.tsx` with:

```tsx
import { useEffect, useState } from 'react'

import './App.css'
import { apiRequest } from './api'

type HealthResponse = {
  status: string
}

type ConnectionState = 'checking' | 'connected' | 'error'

function App() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('checking')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    async function checkConnection() {
      try {
        const response = await apiRequest<HealthResponse>('/health')

        if (response.status === 'ok') {
          setConnectionState('connected')
        } else {
          setErrorMessage('The API reported that it is unavailable.')
          setConnectionState('error')
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'An unknown error occurred.'
        setErrorMessage(message)
        setConnectionState('error')
      }
    }

    void checkConnection()
  }, [])

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Personal finance</p>
        <h1>Finance tracker</h1>
        <p>Record income and spending in one place.</p>
      </header>

      <section className="panel" aria-labelledby="connection-heading">
        <h2 id="connection-heading">Backend connection</h2>

        {connectionState === 'checking' && (
          <p role="status">Checking API connection...</p>
        )}

        {connectionState === 'connected' && (
          <p className="status-success" role="status">
            API and database connected.
          </p>
        )}

        {connectionState === 'error' && (
          <p className="status-error" role="alert">
            Cannot connect: {errorMessage}
          </p>
        )}
      </section>
    </main>
  )
}

export default App
```

### State causes React to render again

`useState` stores a value between renders:

```tsx
const [connectionState, setConnectionState] =
  useState<ConnectionState>('checking')
```

`connectionState` is the current value. `setConnectionState` changes it and
asks React to render the component again. Restricting it to the three string
values in `ConnectionState` prevents impossible spellings or states.

### An effect synchronises with an external system

Rendering calculates what the page should look like. A network request reaches
outside React, so it belongs in an effect:

```tsx
useEffect(() => {
  // perform the request
}, [])
```

The empty dependency array means the effect starts when the component is first
mounted. The `async` work lives in a nested function because an effect itself
must not return a Promise. `void checkConnection()` explicitly says that the
function is started without awaiting its Promise at that line.

The browser's `fetch` rejects for network failures, but a 400 or 500 response is
still a completed HTTP request. That is why `apiRequest` checks `response.ok` and
throws its own error.

## Part 8: run both applications

Use one terminal for Flask:

```sh
cd ~/finance-app/backend
source .venv/bin/activate
FLASK_DEBUG=0 flask --app run run --host 0.0.0.0 --port 5001
```

Use a second terminal for React:

```sh
cd ~/finance-app/frontend
npm run dev
```

Visit `http://localhost:5173`. You should see:

```text
API and database connected.
```

Open the browser developer tools and inspect the Network panel. Select the
`health` request and identify:

- request URL `http://127.0.0.1:5001/api/health`;
- method `GET`;
- status `200`;
- response `{"status":"ok"}`.

This is the same HTTP response previously inspected with `curl`; the caller is
now a browser application.

## Part 9: deliberately check the failure path

Stop Flask with `Ctrl-C`, leaving Vite running. Refresh the browser. The page
should show a connection error instead of remaining stuck on its loading state.

Start Flask again and refresh once more. The success message should return.

If the browser reports a CORS error while both servers are running, confirm:

- React is using `http://localhost:5173`;
- `CORS_ORIGINS` in the backend allows that exact origin;
- the API URL includes port 5001 and `/api`;
- Flask was restarted after backend environment changes.

An origin consists of the scheme, hostname, and port. Consequently,
`http://localhost:5173` and `http://127.0.0.1:5173` are different origins.

## Part 10: lint and build

Keep the development check fast while editing:

```sh
cd ~/finance-app/frontend
npm run lint
```

Then create a production build:

```sh
npm run build
```

The build performs TypeScript checking and writes deployable files under
`frontend/dist/`. The generated `.gitignore` excludes that directory because it
can be recreated.

`npm run dev` is for development only. A later deployment can serve the `dist`
files using a static host while pointing `VITE_API_BASE_URL` at the deployed
Flask API.

## Commit the milestone

Stop the development servers, inspect the changes, and commit them:

```sh
cd ~/finance-app
git status
git add .gitignore frontend
git commit -m "Set up React frontend and API connection"
```

Do not commit `frontend/.env`. Confirm that `git status` does not list it before
committing.

You now have a typed React application that can reach Flask and represent
loading, success, and failure. In Tutorial 2, the health panel will give way to
a transaction history built from the paginated transaction endpoint.
