# Frontend Tutorial 1: build a React page that can talk to Flask

The backend already stores finance data and exposes it through HTTP endpoints.
It now needs a user interface: a page that runs in a browser, asks the backend
for data, and changes what it displays when the answer arrives.

This tutorial builds the smallest version of that loop. The finished page asks
the Flask health endpoint whether the API and database are available. It shows
one message while waiting, another after success, and an error if the request
fails.

The page is intentionally simple. The goal is to understand the path from an
HTML document to a React component and then to an HTTP request. Later tutorials
will reuse that path for real finance data.

Allow about 90 minutes. Make each checkpoint work before moving on. The
checkpoints turn a large block of unfamiliar code into small changes.

## The mental model

During development, four separate systems are involved:

```text
Browser                         Runs HTML, CSS, and JavaScript
  |
  | opens http://localhost:5173
  v
Vite development server        Supplies the frontend files
  |
  | the browser sends GET /api/health
  v
Flask API on port 5001          Runs Python and queries MariaDB
  |
  v
MariaDB                         Stores the data
```

Vite does not call Flask. The JavaScript running in the browser calls Flask.
That distinction helps when debugging: a page can load successfully from Vite
even when Flask is stopped.

The technologies have different jobs:

- **HTML** gives the page meaning and structure: headings, paragraphs, and
  sections.
- **CSS** controls presentation: spacing, colours, widths, and type sizes.
- **JavaScript** adds behaviour, such as starting an HTTP request and reacting
  to its result.
- **TypeScript** checks JavaScript values while you develop. The browser still
  receives JavaScript.
- **React** lets us describe the page as components. When a component's data
  changes, React updates the relevant HTML in the browser.
- **Vite** translates TypeScript and React syntax for the browser, runs the
  development server, and creates production-ready files.
- **npm** installs JavaScript packages and runs project commands.

React does not replace HTML, CSS, or JavaScript. It is a JavaScript library for
coordinating them.

Flask remains responsible for validation, business rules, and database access.
The browser talks to Flask's public HTTP API; it must never connect directly to
MariaDB or receive database credentials.

## Before you start

Complete Backend Tutorial 5 and make sure its tests pass. You also need Node.js
and npm. From the repository root, check that both commands exist:

```sh
cd ~/finance-app
node --version
npm --version
```

Current Vite versions require a current supported Node.js release. Update Node
if Vite later reports that your version is too old.

Create a branch for this milestone:

```sh
git switch -c add-frontend-foundation
```

If you already created `frontend/` while starting this tutorial, keep it and
continue with the next section. Do not scaffold it a second time.

## Part 1: ask Vite to create the starting files

From the repository root, run:

```sh
cd ~/finance-app
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

There are two stages:

1. `npm create vite@latest` generates a project from Vite's `react-ts`
   template. The template saves us from manually configuring TypeScript and
   React's build integration.
2. `npm install` reads `package.json`, downloads the listed packages into
   `node_modules/`, and records exact versions in `package-lock.json`.

The standalone `--` tells npm to pass `--template react-ts` to Vite instead of
interpreting that option itself.

Start the development server:

```sh
npm run dev
```

Open `http://localhost:5173`. You should see Vite's starter page. Leave this
terminal running. When a source file changes, Vite rebuilds it and refreshes
the browser.

### What did the template create?

You do not need to understand every generated file yet. These are the ones we
will touch:

```text
frontend/
  index.html              first document opened by the browser
  package.json            packages and commands for this project
  package-lock.json       exact package versions installed by npm
  vite.config.ts          connection between Vite and React
  tsconfig.json           TypeScript settings
  src/
    main.tsx              starts React
    App.tsx               describes our page
    index.css             defaults for the whole document
    App.css               styles for the App component
```

The `.tsx` extension means a TypeScript file may also contain JSX, the
HTML-like syntax used by React.

`node_modules/` is large but reproducible from the lock file, so Git ignores
it. Think of `package.json` and `package-lock.json` as the recipe and
`node_modules/` as the prepared result.

### Checkpoint

At this point only Vite is running. The starter page should work even if Flask
is stopped. If it does not, solve that before adding application code.

## Part 2: trace the route from HTML to React

Before replacing anything, follow how the starter page reaches the screen.

Open `frontend/index.html`. It contains an empty element:

```html
<div id="root"></div>
```

and loads this module near the bottom:

```html
<script type="module" src="/src/main.tsx"></script>
```

The browser first creates the empty `div`. Vite then processes `main.tsx` and
loads the resulting JavaScript module.

Now open `frontend/src/main.tsx`. Its important expression is:

```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

Read it from the inside out:

1. `document.getElementById('root')` finds the `div` from `index.html`.
2. The `!` is a TypeScript assurance that the element is present. We can make
   that assurance because we just saw it in `index.html`.
3. `createRoot(...)` gives React control of that element.
4. `.render(...)` asks React to put the `App` component inside it.

`<App />` resembles an HTML tag, but its capital letter tells React that it is
a component defined by our code. Lowercase names such as `<main>` refer to real
HTML elements.

`StrictMode` adds development-only checks. It may run component setup and
cleanup an extra time, so you may later see two health requests in the Network
panel. It does not do that in a production build.

The complete path is:

```text
index.html -> main.tsx -> App.tsx -> HTML elements on screen
```

## Part 3: make the component describe our page

We will begin with content and no custom styling. This keeps two questions
separate: is the right information on the page, and does it look right?

Replace `frontend/src/App.tsx` with:

```tsx
function App() {
  return (
    <main>
      <header>
        <p>Personal finance</p>
        <h1>Finance tracker</h1>
        <p>Record income and spending in one place.</p>
      </header>

      <section aria-labelledby="connection-heading">
        <h2 id="connection-heading">Backend connection</h2>
        <p>Connection check not started.</p>
      </section>
    </main>
  )
}

export default App
```

Save the file and inspect the browser. It should show plain, mostly unstyled
text.

### Why is this a function?

A React component is a JavaScript function. Calling `App()` calculates a
description of what should be on screen. React calls it for us and turns its
returned JSX into browser elements.

The `export default` line makes the function available to the import in
`main.tsx`.

### Why these HTML elements?

- `<main>` identifies the primary content of this page.
- `<header>` groups the page introduction.
- `<h1>` is the page's main heading. There should normally be one.
- `<section>` groups the connection feature.
- `<h2>` names that section and creates a sensible heading hierarchy.
- `aria-labelledby` gives the section the name from the element whose ID is
  `connection-heading`.

JSX is close to HTML, but it is part of JavaScript. A component must return one
outer element, which is why `<main>` encloses the header and section. Later,
JavaScript expressions will appear between braces: `{someValue}`.

### Checkpoint

Use the browser's Elements panel. You should find a real `main`, `header`, and
`section` inside `<div id="root">`. React created them from the JSX.

## Part 4: add CSS with a reason for every rule

CSS rules have this shape:

```css
selector {
  property: value;
}
```

The selector chooses elements. The declarations inside the braces say how
those elements should look. We will set document-wide defaults and then style
this component.

It also helps to picture the CSS box model. From outside to inside, an element
has these layers:

```text
margin -> border -> padding -> content
```

Margin separates an element from its neighbours. Padding creates space inside
its border. Width normally describes the content box; the `box-sizing` rule
below will make width easier to reason about.

### Set predictable document defaults

Replace `frontend/src/index.css` with:

```css
:root {
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #17202a;
  background: #f4f7f6;
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

These rules solve specific problems:

- `:root` selects the document's top-level element. Text colour and font are
  inherited by its children, so this is one place to establish defaults.
- The `font-family` list contains fallbacks. The browser uses the first font
  available; `sans-serif` is the final generic fallback.
- Hex values such as `#17202a` describe colours using red, green, and blue.
- `*` selects every element. `box-sizing: border-box` makes a declared width
  include padding and borders. Without it, padding can unexpectedly make a box
  wider than its declared width.
- Browsers give `<body>` a small default margin. `margin: 0` removes it so our
  layout controls the page edge deliberately.
- `100vh` means 100% of the viewport height. The body fills the screen even
  when there is little content.
- The 320-pixel minimum prevents the layout being squeezed below a reasonable
  narrow-phone width.
- Form controls do not reliably inherit the page font, so `font: inherit`
  makes future controls match. It has no visible effect yet.

`index.css` applies because `main.tsx` imports it. Importing CSS from JavaScript
is a Vite feature: Vite includes that stylesheet in the build.

### Add hooks for component-specific styling

Update `App.tsx` to add class names:

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

In HTML the attribute is `class`; in JSX it is `className`. Class names carry
no built-in appearance. They are labels that CSS can select. The import makes
the rules in `App.css` part of the page.

### Constrain and centre the content

Replace `frontend/src/App.css` with this first rule:

```css
.app-shell {
  width: min(70rem, calc(100% - 2rem));
  margin: 0 auto;
  padding: 3rem 0;
}
```

The leading dot means “an element with this class.”

- `width: min(...)` chooses the smaller width. Content can be at most `70rem`,
  but on a narrow screen it uses the viewport width minus `2rem`, leaving a
  `1rem` gap on each side.
- A `rem` is based on the document's root font size, so it scales with the
  user's font preference.
- `margin: 0 auto` uses no vertical margin and divides spare horizontal space
  equally on both sides, centring the box.
- `padding: 3rem 0` puts space inside the box above and below its content.

Save and resize the browser. The content should remain centred, stop growing
on a wide screen, and retain side space on a narrow one.

### Create visual hierarchy

Append these rules:

```css
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
```

The title should dominate, the description should recede, and the small label
should identify the product area.

- A space in `.page-header h1` means “an `h1` inside `.page-header`.”
- Headings have browser-default margins. Setting the title's margin to zero
  gives us predictable spacing.
- `clamp(minimum, preferred, maximum)` lets the title respond to screen width.
  Here `5vw` means 5% of the viewport width, bounded by `2rem` and `3.5rem`.
- `p:last-child` selects only the final paragraph in the header.
- Weight `700`, uppercase letters, and wider letter spacing distinguish the
  small eyebrow without making it large.

### Make the connection area a panel

Append:

```css
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

The border and white background separate the result from the page. Padding
creates room inside that boundary. Border radius rounds its corners. The four
shadow values mean horizontal offset, vertical offset, blur radius, and
colour; `/ 8%` makes the colour mostly transparent.

The status classes are not used yet. The next part will attach them to success
and error messages. Colour is only an extra cue—the wording will state what
happened too.

### Checkpoint

You should now have the finished visual shell, still showing “Connection check
not started.” If the content is correct but unstyled, check the CSS import and
class names first.

Unused starter images may remain in `src/assets`. Since no file imports them,
Vite will not include them in the page.

## Part 5: keep the API address outside the source code

During development the frontend page is at port 5173 and Flask is at port
5001. The browser needs Flask's complete base address.

Create `frontend/.env.example`:

```text
VITE_API_BASE_URL=http://127.0.0.1:5001/api
```

Create a local `frontend/.env` with the same content:

```text
VITE_API_BASE_URL=http://127.0.0.1:5001/api
```

Why use configuration instead of writing this address inside every request?
The deployed API will have a different address. Configuration lets the same
source code work in both environments.

- `.env.example` documents the required setting and is committed.
- `.env` supplies your local value and is not committed.

The root `.gitignore` already ignores `.env` and `.env.*` while allowing files
ending in `.example`. Confirm with:

```sh
cd ~/finance-app
git status --short
```

`frontend/.env.example` may appear; `frontend/.env` must not.

Vite exposes variables beginning with `VITE_` to browser code. That means every
user can read them. An API URL is safe there. A database password, API secret,
or private key is not.

Restart `npm run dev` after adding or changing an environment file. Vite reads
these files when it starts.

## Part 6: learn the request in the browser console

Before hiding HTTP details behind a helper, try the browser API directly. Start
Flask in a separate terminal:

```sh
cd ~/finance-app/backend
source .venv/bin/activate
FLASK_DEBUG=0 flask --app run run --host 0.0.0.0 --port 5001
```

Open the browser developer tools on the frontend page, select Console, and run:

```js
const response = await fetch('http://127.0.0.1:5001/api/health')
response.status
await response.json()
```

You should see status `200` and then `{status: 'ok'}`.

`fetch` starts an HTTP request and returns a `Promise`: an object representing
a result that will arrive later. `await` pauses this console snippet until the
result arrives. The first result is a `Response`, containing HTTP status and
headers. Calling `response.json()` asynchronously reads and parses its body.

This experiment proves the browser can reach Flask before React is involved.

## Part 7: centralise HTTP behaviour in one helper

Later screens will make many requests. Repeating the base URL, status checks,
JSON parsing, and error handling in every component would make them noisy and
inconsistent. We will put those transport concerns in one function.

Create `frontend/src/api.ts` in the following stages.

### Read the base URL

Start with:

```ts
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:5001/api'
```

`import.meta.env` is how Vite makes environment values available to source
code. `??` uses the value on its right only when the left value is `null` or
`undefined`. The fallback is useful if `.env` is absent.

### Represent unsuccessful HTTP responses

Append:

```ts
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
```

The backend normally describes an error as `{ "error": "message" }`.
`ApiErrorResponse` tells TypeScript that such an object may contain an `error`
string. `?` means the property is optional because an unexpected server
response might not follow that shape.

JavaScript's normal `Error` holds a message but no HTTP status. `ApiError`
extends it so later code can use both. `readonly` prevents code from changing
the status after construction. The constructor runs when code uses
`new ApiError(...)`: `super(message)` initializes the normal `Error` part, and
`this.status = status` stores the extra field on this particular error object.

### Send a request and handle success or failure

Append:

```ts
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

Follow one request through the function:

1. The caller supplies a short path such as `/health`.
2. A template literal, written with backticks and `${...}`, joins it to the
   base URL.
3. `await fetch(...)` waits for the HTTP response.
4. `response.ok` is true for statuses 200 through 299. `fetch` rejects for a
   network failure but does **not** reject merely because a server returns 404
   or 500, so we check this ourselves.
5. On failure, we start with a reliable status message. The `try` block replaces
   it with the backend's message when possible. The empty `catch` retains the
   fallback for HTML or empty error responses.
6. On success, we parse and return JSON.

The remaining syntax makes the helper reusable:

- `async` means the function returns a Promise.
- `<T>` is a type placeholder chosen by each caller. It can describe health
  data now and transaction data later.
- `Promise<T>` says that awaiting the function produces that chosen type.
- `RequestInit` is the browser's type for optional `fetch` settings such as
  method, headers, and body.
- The `?` after `options` means callers may omit that argument. A simple GET
  needs no options; later POST requests will supply them.
- `export` makes `ApiError` and `apiRequest` available to other source files.
- A successful `204 No Content` has no JSON to parse. Returning `undefined`
  supports deletion in Tutorial 6.

Type assertions written with `as` tell TypeScript how we expect untyped JSON to
look. They do not validate it at runtime. The backend contract and tests remain
responsible for returning the documented shape.

## Part 8: let component state drive the screen

The message changes over time:

```text
checking -> connected
         -> error
```

Changing an ordinary local variable would neither tell React to update the
page nor preserve the value when React calls the component again. React
**state** does both.

Replace `App.tsx` with this version, which still makes no request:

```tsx
import { useState } from 'react'

import './App.css'

type ConnectionState = 'checking' | 'connected' | 'error'

function App() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('checking')

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Personal finance</p>
        <h1>Finance tracker</h1>
        <p>Record income and spending in one place.</p>
      </header>

      <section className="panel" aria-labelledby="connection-heading">
        <h2 id="connection-heading">Backend connection</h2>
        <p role="status">Current state: {connectionState}</p>
      </section>
    </main>
  )
}

export default App
```

`ConnectionState` permits exactly three strings. A typo such as `'conected'`
will fail TypeScript checking.

`useState` returns two items in an array. Array destructuring names them:

- `connectionState` is the value for the current render;
- `setConnectionState` changes it and schedules a new render.

The argument `'checking'` is the initial value. In JSX,
`{connectionState}` switches into JavaScript and displays the current string.
`role="status"` asks assistive technology to announce updated status text.

Replace the single status paragraph with three conditions:

```tsx
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
    Cannot connect.
  </p>
)}
```

In JavaScript, `condition && value` produces `value` only when the condition is
true. React ignores `false`, so one paragraph renders for the current state.
Errors use `role="alert"` because they need more immediate announcement. The
wording communicates the outcome without relying on colour alone.

The page remains on “Checking” for now. We have built the display logic; next
we add the event that changes it.

## Part 9: start the request when the component appears

Rendering should calculate UI. An HTTP request communicates with something
outside React, so React calls it a **side effect**. `useEffect` runs that work
after a render is placed on the page.

First update the imports and describe the successful JSON:

```tsx
import { useEffect, useState } from 'react'

import './App.css'
import { apiRequest } from './api'

type HealthResponse = {
  status: string
}
```

An `import` brings a value exported by another module into this file. Braces
mean these are named exports: React exports `useEffect` and `useState`, and our
`api.ts` exports `apiRequest`. Importing the CSS asks Vite to include the
stylesheet; CSS does not provide a JavaScript name, so that import has no
braces.

`HealthResponse` documents what this endpoint returns and lets TypeScript
check later use of `response.status`. Like every TypeScript type, it disappears
from the JavaScript sent to the browser.

Inside `App`, directly after the existing `useState`, add state for error
detail:

```tsx
const [errorMessage, setErrorMessage] = useState('')
```

Keeping phase and message separate lets the phase select the interface while
the message preserves diagnostic detail.

Then add this effect below the state declarations:

```tsx
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
```

Read the lifecycle in order:

1. React calls `App` with initial state `'checking'`.
2. React puts the checking paragraph on screen.
3. The effect calls `apiRequest('/health')`.
4. The browser remains responsive while `await` waits.
5. A successful `{ "status": "ok" }` changes state to `'connected'`.
6. A bad response or network failure records a message and changes state to
   `'error'`.
7. A setter causes React to call `App` again and update the paragraph.

Why a nested async function? An effect may return a cleanup function, but an
`async` function always returns a Promise. Keeping `async` on
`checkConnection` avoids giving React a Promise where it expects cleanup.

The empty dependency array `[]` means there are no changing values that should
rerun this effect. It runs when the component mounts. In development,
`StrictMode` may deliberately mount it twice to expose unsafe effects.

`void checkConnection()` explicitly discards the Promise at that line. Errors
from the awaited request are handled inside the function.

The `catch` variable has the safe type `unknown`. `instanceof Error` checks it
at runtime before reading `.message`; the fallback covers JavaScript's ability
to throw any value.

Finally, change the error paragraph to display the detail:

```tsx
{connectionState === 'error' && (
  <p className="status-error" role="alert">
    Cannot connect: {errorMessage}
  </p>
)}
```

## Part 10: compare the completed component

Your final `frontend/src/App.tsx` should be:

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

This listing is a reference, not a new step to copy. If yours differs, compare
one section at a time and identify what each difference changes.

## Part 11: inspect success and failure

Keep Flask running in one terminal and start or restart Vite in another:

```sh
cd ~/finance-app/frontend
npm run dev
```

Visit `http://localhost:5173`. The checking message may appear only briefly,
followed by:

```text
API and database connected.
```

Open developer tools, select Network, and inspect the `health` request:

- Request URL: `http://127.0.0.1:5001/api/health`
- Method: `GET`
- Status: `200`
- Response: `{"status":"ok"}`

This is the same response previously inspected with `curl`; its caller is now
JavaScript in a browser.

Stop Flask with `Ctrl-C`, leave Vite running, and refresh. The page should show
an error instead of remaining stuck on loading. This deliberate failure proves
the error branch works. Start Flask and refresh again to restore success.

### If the browser reports a CORS error

CORS is a browser security rule. The frontend's origin differs from the API's
because the ports differ, so Flask must permit the frontend origin.

Confirm:

- the page is open at `http://localhost:5173`;
- the backend's `CORS_ORIGINS` allows that exact origin;
- `VITE_API_BASE_URL` includes port 5001 and `/api`;
- both servers were restarted after environment changes.

An origin combines scheme, hostname, and port. Therefore
`http://localhost:5173` and `http://127.0.0.1:5173` are different origins.

Use the symptom to choose where to look:

| Symptom | Likely layer |
| --- | --- |
| Vite starter page still appears | `App.tsx` was not saved or the wrong server is open |
| Correct content, no styles | missing CSS import or mismatched class name |
| Page loads, request says connection refused | Flask is stopped or the URL/port is wrong |
| Browser explicitly mentions CORS | backend does not allow the page's exact origin |
| Request succeeds but UI stays on checking | effect, response test, or state update is wrong |

## Part 12: ask the tools to check the project

Run the linter:

```sh
cd ~/finance-app/frontend
npm run lint
```

The linter looks for suspicious code and violations of React and TypeScript
rules. It complements TypeScript: types can be valid while a pattern is still
error-prone.

Then create a production build:

```sh
npm run build
```

This first checks TypeScript and then asks Vite to write optimized browser
files under `frontend/dist/`. Git ignores that directory because it can be
recreated.

`npm run dev` is a development tool, not the deployed application. A later
deployment will serve the static files from `dist` and build them with
`VITE_API_BASE_URL` pointing at the deployed Flask API.

## Commit the milestone

Stop the development servers, inspect the changes, and commit them:

```sh
cd ~/finance-app
git status
git add .gitignore frontend
git commit -m "Set up React frontend and API connection"
```

Before committing, confirm that `frontend/.env` is not listed. It is local
configuration and must remain untracked.

You can now trace the whole mechanism:

```text
HTML root
  -> React renders App
  -> App initially renders the checking state
  -> an effect calls the shared API helper
  -> fetch sends HTTP to Flask
  -> a state setter records the result
  -> React renders the matching success or error message
```

Tutorial 2 will reuse this mechanism, replacing the health response with a
paginated transaction response and splitting the interface into smaller
components.
