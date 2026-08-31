# Tutorial 4: test the React frontend

The frontend can now list transactions and create a new one. Until now, you
have checked those behaviours by clicking around in the browser. In this
tutorial you will make those checks repeatable with automated tests.

You will test what a person can see and do: loading text appears, transactions
are displayed, errors are explained, and submitting the form adds the saved
transaction. The tests will replace the real API at the network boundary, so
neither Flask nor MariaDB needs to be running.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Understand frontend testing | 10 minutes |
| Install and configure the tools | 15 minutes |
| Study two guided examples | 10 minutes |
| Complete the exercises | 20 minutes |
| Run the full suite and commit | 5 minutes |

## What kind of tests are these?

The tests render real React components in a simulated browser page. They then
use the interface in much the same way as a person would:

```text
Vitest -> React Testing Library -> App -> fetch -> MSW's mock API
```

The main tools have separate jobs:

- **Vitest** finds test files, runs tests, and reports failures. It works well
  with a Vite project.
- **jsdom** gives the tests a browser-like document without opening a real
  browser.
- **React Testing Library** renders components and finds visible elements.
- **user-event** performs realistic clicks and typing.
- **jest-dom** adds readable assertions such as `toBeInTheDocument()`.
- **Mock Service Worker (MSW)** intercepts HTTP requests and returns controlled
  responses.

These are component integration tests. Each test exercises several components,
React state, and the real `apiRequest` helper together. Only the external API is
replaced. This gives more confidence than testing each component's private
functions, while remaining fast and deterministic.

## Part 1: understand the core concepts

### Test behaviour, not implementation

A useful frontend test asks what a person observes:

```text
Given the API has one transaction
When the transactions page finishes loading
Then its description and amount are visible
```

Like the backend tests, each test is a small Arrange–Act–Assert story:

- **Arrange:** choose the mock API response and render the component.
- **Act:** click, type, or wait for the initial request.
- **Assert:** check the page or the request that the action produced.

Avoid assertions about state variable names, component nesting, or whether a
particular hook ran. Those details can change during a refactor even though the
application still behaves correctly.

### Prefer accessible queries

React Testing Library's `screen` object searches the rendered page. Prefer
queries based on how people and assistive technology identify an element:

```tsx
screen.getByRole("button", { name: "Add transaction" });
screen.getByLabelText("Amount");
screen.getByText("Weekly shop");
```

`getByRole` is usually the strongest choice. It encourages semantic HTML and
checks an element's accessible name. `getByLabelText` is a natural choice for a
form control. Text queries are useful for ordinary content.

Do not add a `data-testid` merely because a role or label takes a little more
thought. A test that cannot find a form field by its label may have revealed an
accessibility problem in the interface.

The three common query families describe different expectations:

| Query | Use it when | Result |
| --- | --- | --- |
| `getBy...` | The element must exist now | Returns it or throws immediately |
| `queryBy...` | The element may not exist | Returns it or `null` |
| `findBy...` | The element will appear later | Returns a promise |

### React updates asynchronously

The app fetches data after its first render. The response arrives later and
causes another render, so this assertion is asynchronous:

```tsx
expect(await screen.findByText("Weekly shop")).toBeInTheDocument();
```

`await` pauses the test until the promise settles. `findByText` keeps checking
for a short period instead of failing immediately.

To prove that something disappears, use `waitFor` with a query that is allowed
to return `null`:

```tsx
import { screen, waitFor } from "@testing-library/react";

await waitFor(() => {
  expect(screen.queryByText("Loading transactions…")).not.toBeInTheDocument();
});
```

Use asynchronous helpers only for changes that actually happen later. An
immediate assertion should remain immediate because its failure is clearer.

### Mock at the network boundary

It is tempting to replace `apiRequest` with a fake function. MSW instead
intercepts the request made by the real helper:

```text
App -> apiRequest -> fetch -> MSW handler -> mock response
```

The test therefore still checks the URL, HTTP method, JSON parsing, error
handling, and the React behaviour that follows. It does not depend on a running
backend or alter development data.

Most tests will use sensible default responses. A particular test can override
one endpoint to create an empty result or an error. MSW removes those overrides
after each test so tests do not leak state into one another.

## Part 2: install and configure the test environment

Start from the result of Tutorial 3 and create a branch:

```sh
cd ~/finance-app
git switch -c add-frontend-tests
cd frontend
```

Install the test-only packages:

```sh
npm install --save-dev vitest jsdom @testing-library/react \
  @testing-library/jest-dom @testing-library/user-event msw
```

`--save-dev` records packages needed while developing and testing, but not by
the application in a production browser.

### Add the test commands

In `frontend/package.json`, add two entries to the existing `scripts` object.
Keep the existing `dev`, `build`, `lint`, and `preview` entries:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

JSON does not allow comments or a trailing comma after the final entry.

- `npm test` runs the suite once and exits, which is suitable before a commit
  and in continuous integration.
- `npm run test:watch` stays open, watches saved files, and reruns affected
  tests while you work. Press `q` to quit.

### Configure Vitest

Replace `frontend/vite.config.ts` with:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
```

Vitest understands Vite's configuration, so the React plugin and test settings
can live in one file. Importing `defineConfig` from `vitest/config` adds the
TypeScript type for the `test` property. `environment: "jsdom"` supplies the
browser-like document, and `setupFiles` names code that runs before every test
file.

### Create the test setup file

Create `frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

afterEach(() => {
  server.resetHandlers();
  cleanup();
});

afterAll(() => server.close());
```

The first import installs jest-dom's matchers into Vitest's `expect` function.
The three lifecycle functions manage the mock server:

- `beforeAll` starts it once before the file's tests run.
- `afterEach` removes handler overrides and the rendered page after each test.
- `afterAll` closes it after the suite.

`onUnhandledRequest: "error"` turns an unexpected request into a useful test
failure. A misspelled URL should not silently reach a real server.

### Define reusable mock data

Create `frontend/src/test/fixtures.ts`:

```ts
import type { Category, Transaction } from "../types";

export const groceriesCategory: Category = {
  id: 2,
  description: "Groceries",
  category_type: "spending",
};

export const weeklyShop: Transaction = {
  id: 10,
  amount: "42.75",
  transaction_date: "2026-08-20",
  description: "Weekly shop",
  category_id: groceriesCategory.id,
  category: groceriesCategory,
};
```

The fixture uses the application types, so TypeScript warns you if mock data no
longer matches an API response.

### Add the default request handlers

Create `frontend/src/test/handlers.ts`:

```ts
import { http, HttpResponse } from "msw";

import { groceriesCategory, weeklyShop } from "./fixtures";

export const handlers = [
  http.get("*/api/transactions", () => {
    return HttpResponse.json({
      data: [weeklyShop],
      pagination: {
        page: 1,
        per_page: 20,
        total_items: 1,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      },
    });
  }),

  http.get("*/api/categories", () => {
    return HttpResponse.json({ data: [groceriesCategory] });
  }),
];
```

The `*` matches whichever API origin was configured in Tutorial 1 while still
requiring the exact `/api/...` path. These defaults make the app start with one
category and one transaction. Individual tests can temporarily replace either
handler.

Create `frontend/src/test/server.ts`:

```ts
import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

`setupServer` is MSW's Node.js integration. Despite its name, it does not start
an HTTP port; it intercepts the requests made inside the test process.

Your test infrastructure should now look like this:

```text
frontend/
├── src/
│   └── test/
│       ├── fixtures.ts
│       ├── handlers.ts
│       ├── server.ts
│       └── setup.ts
├── package.json
└── vite.config.ts
```

Run `npm test`. Vitest should report that no test files were found. The non-zero
exit status is expected until you add the first test in the next section.

## Part 3: study two guided examples

Create `frontend/src/App.test.tsx` and begin with these imports:

```tsx
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import App from "./App";
import { server } from "./test/server";
```

`describe` groups related tests. `it` defines one behaviour, and `expect`
checks the result. A file ending in `.test.tsx` is discovered by Vitest; the
`x` is needed because the file renders JSX.

### Example 1: loading and displaying transactions

Add the first test:

```tsx
describe("App", () => {
  it("shows a loading state and then lists transactions", async () => {
    render(<App />);

    expect(screen.getByText("Loading transactions…")).toBeInTheDocument();

    expect(await screen.findByText("Weekly shop")).toBeInTheDocument();
    expect(screen.getByText("−£42.75")).toBeInTheDocument();
    expect(
      screen.queryByText("Loading transactions…"),
    ).not.toBeInTheDocument();
  });
});
```

The loading assertion uses `getByText` because loading is visible immediately.
The description uses `findByText` because it appears after the mock response.
Once that promise resolves, the other assertions can use synchronous queries.
The transaction is spending, so the row formatter from Tutorial 2 places a
Unicode minus sign (`−`) before the formatted pound amount.

This test deliberately does not ask whether `useEffect` ran or inspect the
component's state. It checks the behaviour that state and the effect produce.

Run only this file:

```sh
npm test -- src/App.test.tsx
```

### Example 2: displaying an API error

Add a second test inside the same `describe` block:

```tsx
it("explains when transactions cannot be loaded", async () => {
  server.use(
    http.get("*/api/transactions", () => {
      return HttpResponse.json(
        { error: "The database is unavailable." },
        { status: 500 },
      );
    }),
  );

  render(<App />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The database is unavailable.",
  );
  expect(screen.queryByText("Weekly shop")).not.toBeInTheDocument();
});
```

`server.use` adds a handler with priority over the default for this test. The
setup file resets it afterwards. The application still makes a real `fetch`
call and the real API helper turns the unsuccessful response into an error.

Finding the message by the `alert` role also checks that important errors are
announced to assistive technology. Tutorial 2 added that role to the error
message; the test now protects it.

## Part 4: your exercises

Spend about 20 minutes on these tests before reading the reference solution.
Keep them in the existing `describe("App", ...)` block.

### Exercise A: the empty state

Write a test named `shows guidance when there are no transactions`:

1. Override `GET */api/transactions`.
2. Return an empty `data` array and pagination values for zero results.
3. Render `App`.
4. Find the text `No transactions yet.` asynchronously.
5. Prove that the default fixture `Weekly shop` is absent.

Why must the empty-state assertion use `findByText` rather than `getByText`?

### Exercise B: submit the creation form

Write a test named `creates a transaction from the form`:

1. Create a `user` with `userEvent.setup()`.
2. Keep a local boolean that records whether the POST has succeeded.
3. Override `POST */api/transactions`, inspect its JSON body, set the boolean,
   and return a saved transaction with ID `11` and status `201`.
4. Override `GET */api/transactions` so the saved transaction appears after
   that boolean changes. This represents the authoritative refetch from
   Tutorial 3.
5. Render `App` and wait for the initial list to load.
6. Fill Amount with `18.50`, Date with `2026-08-21`, Description with
   `Lunch with Sam`, and choose `Groceries` from Category.
7. Click `Add transaction`.
8. Find `Lunch with Sam` in the updated list and check its formatted amount.

Add this import at the top of the test file:

```tsx
import userEvent from "@testing-library/user-event";
```

Useful calls are:

```tsx
await user.type(screen.getByLabelText("Amount"), "18.50");
await user.selectOptions(screen.getByLabelText("Category"), "2");
await user.click(screen.getByRole("button", { name: "Add transaction" }));
```

Every `user` action is asynchronous, so remember `await`. Do not call the form
component's submit function directly: using its controls also verifies that
labels, values, events, and button all work together.

Before viewing the solution, run `npm test -- src/App.test.tsx` and read the
first failure carefully. A testing failure shows the accessible page at the
time of the failed query, which is often enough to spot an incorrect label or
unexpected response.

## Part 5: reference solution

This is one clear solution. Your handler variable names may differ while
testing the same behaviour.

Add `userEvent` to the imports shown earlier, then add the following tests.

### Empty-state solution

```tsx
it("shows guidance when there are no transactions", async () => {
  server.use(
    http.get("*/api/transactions", () => {
      return HttpResponse.json({
        data: [],
        pagination: {
          page: 1,
          per_page: 20,
          total_items: 0,
          total_pages: 0,
          has_next: false,
          has_previous: false,
        },
      });
    }),
  );

  render(<App />);

  expect(await screen.findByText("No transactions yet.")).toBeInTheDocument();
  expect(screen.queryByText("Weekly shop")).not.toBeInTheDocument();
});
```

The empty state depends on a completed request, so it is not present during the
first render. That is why `findByText` is appropriate.

### Form-submission solution

```tsx
it("creates a transaction from the form", async () => {
  const user = userEvent.setup();
  const savedTransaction = {
    id: 11,
    amount: "18.50",
    transaction_date: "2026-08-21",
    description: "Lunch with Sam",
    category_id: groceriesCategory.id,
    category: groceriesCategory,
  };
  let hasBeenCreated = false;

  server.use(
    http.post("*/api/transactions", async ({ request }) => {
      expect(await request.json()).toEqual({
        amount: "18.50",
        transaction_date: "2026-08-21",
        description: "Lunch with Sam",
        category_id: 2,
      });

      hasBeenCreated = true;
      return HttpResponse.json(
        { data: savedTransaction },
        { status: 201 },
      );
    }),
    http.get("*/api/transactions", () => {
      const data = hasBeenCreated
        ? [savedTransaction, weeklyShop]
        : [weeklyShop];

      return HttpResponse.json({
        data,
        pagination: {
          page: 1,
          per_page: 20,
          total_items: data.length,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
      });
    }),
  );

  render(<App />);
  await screen.findByText("Weekly shop");

  const categorySelect = await screen.findByLabelText("Category");

  await user.type(screen.getByLabelText("Amount"), "18.50");
  await user.type(screen.getByLabelText("Date"), "2026-08-21");
  await user.type(screen.getByLabelText("Description"), "Lunch with Sam");
  await user.selectOptions(categorySelect, "2");
  await user.click(screen.getByRole("button", { name: "Add transaction" }));

  expect(await screen.findByText("Lunch with Sam")).toBeInTheDocument();
  expect(screen.getByText("−£18.50")).toBeInTheDocument();
});
```

Add the fixture import used by the response:

```tsx
import { groceriesCategory, weeklyShop } from "./test/fixtures";
```

The assertion inside the POST handler proves that the browser sent the API
contract expected by Flask. Changing `hasBeenCreated` makes the following GET
return the server's new first page. The assertions after the click therefore
also prove that the form triggered the authoritative refresh without coupling
the test to component state.

## Part 6: run all project checks

Run the tests once:

```sh
npm test
```

A successful result will resemble:

```text
✓ src/App.test.tsx (4 tests)

Test Files  1 passed (1)
     Tests  4 passed (4)
```

The exact timings and symbols can differ. Then run the checks already supplied
by the Vite project:

```sh
npm run lint
npm run build
```

Tests, linting, and compilation catch different problems:

- Tests check visible behaviour for the stories you wrote.
- ESLint checks suspicious JavaScript and React patterns.
- The build checks TypeScript and proves Vite can create production assets.

If Vitest says a request was unhandled, compare its printed method and URL with
the handlers in `src/test/handlers.ts`. If a query finds several elements, make
it more specific with a role and accessible name instead of selecting the first
match.

## Commit the milestone

Inspect and commit the test setup and tests:

```sh
cd ~/finance-app
git status --short
git diff
git add frontend/package.json frontend/package-lock.json \
  frontend/vite.config.ts frontend/src/test frontend/src/App.test.tsx \
  docs/frontend/04-frontend-testing-tutorial.md
git commit -m "Add frontend component tests"
git push -u origin add-frontend-tests
```

You now have a safety net around the frontend's first two user journeys. When a
later tutorial adds filters, editing, or navigation, keep using the same
pattern: arrange an API response, act through accessible controls, and assert
the result a person can observe.
