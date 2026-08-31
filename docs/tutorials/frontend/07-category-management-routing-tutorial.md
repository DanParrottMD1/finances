# Tutorial 7: add category management and routing

The application now has a complete transaction workflow. In this tutorial you
will give categories their own screen and add navigation between two meaningful
pages:

```text
/             Transactions
/categories   Categories
```

The Categories page will list income and spending categories in separate
groups and create new categories through `POST /api/categories`. When you
return to Transactions, the category selector will fetch the current list and
include anything you just created.

This is the right time to introduce client-side routing. Earlier, a router
would only have added configuration. The application now genuinely has two
destinations with different purposes.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Understand routing and page composition | 10 minutes |
| Add the router, layout, and category hook | 15 minutes |
| Build the Categories page | 15 minutes |
| Complete the testing exercise | 15 minutes |
| Verify and commit | 5 minutes |

## What we are building

The component hierarchy will become:

```text
BrowserRouter
└── App
    └── AppLayout
        ├── shared navigation
        └── Outlet
            ├── TransactionsPage
            │   └── existing filters, form, list, edit, and delete UI
            └── CategoriesPage
                ├── CategoryForm
                └── income and spending groups
```

`App` will match the browser URL to a page. `AppLayout` supplies the elements
that stay on screen during navigation. The `Outlet` marks the position where
the matched page is rendered.

Each page that needs categories will call the same small `useCategories` hook.
The hook shares *logic*, not global state. Navigating away unmounts one page;
navigating back mounts the other page and performs a fresh GET. This simple
server-first design is sufficient for two screens and needs neither Context nor
a global state library.

## Part 1: understand the React concepts

### Client-side routing

A normal link can ask the server for an entirely new HTML document. A React
router instead watches the URL and swaps the matched page without discarding
the running application.

React Router's declarative pieces have distinct jobs:

- `BrowserRouter` connects React Router to the browser address bar and history.
- `Routes` chooses the best matching `Route`.
- `Route` maps a URL path to an element.
- `NavLink` navigates and reports whether its destination is active.
- `Outlet` renders a matched child route inside its parent layout.
- `Link` is navigation within ordinary page content.

The URL remains useful: `/categories` can be bookmarked, refreshed, or shared.
The browser Back and Forward buttons continue to work.

### Pages compose existing components

A page is still an ordinary React component. The name describes its role, not
a special React type. `TransactionsPage` coordinates transaction features;
`CategoriesPage` coordinates category features. Smaller components continue to
own focused pieces of interface.

```text
page: fetches and coordinates a feature
component: renders or performs one focused part of that feature
layout: surrounds several pages with shared interface
```

### A custom hook reuses stateful logic

A custom hook is a function whose name starts with `use` and which may call
other hooks. Extracting category loading prevents two pages from copying the
same `useState`, `useEffect`, and error-handling code.

It does not create a singleton. Each caller owns an independent state instance.
That behaviour is useful here: returning to Transactions mounts the page again,
so it reads the authoritative category list from Flask.

## Part 2: add the routing plumbing

Start from the end of Tutorial 6:

```sh
cd ~/finance-app
git switch -c add-category-management
cd frontend
npm install react-router-dom
mkdir -p src/hooks src/pages
```

`react-router-dom` is an application dependency because the production browser
uses it, so do not add `--save-dev`.

### Put the router at the application boundary

In `frontend/src/main.tsx`, add the `BrowserRouter` import and wrap `App`. Keep
the existing stylesheet import:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
```

There should be exactly one router around the application. Tests will supply a
`MemoryRouter` instead because they do not use a real address bar.

### Create the shared layout

Create `frontend/src/components/AppLayout.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom";

function navigationClassName({ isActive }: { isActive: boolean }) {
  return isActive ? "site-navigation__link is-active" : "site-navigation__link";
}

export function AppLayout() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <p className="eyebrow">Personal finance</p>
        <nav className="site-navigation" aria-label="Primary navigation">
          <NavLink className={navigationClassName} to="/" end>
            Transactions
          </NavLink>
          <NavLink className={navigationClassName} to="/categories">
            Categories
          </NavLink>
        </nav>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  );
}
```

The `end` prop prevents the `/` link from remaining active at every URL that
starts with `/`. `aria-label` gives the navigation landmark a useful name.

### Turn App into the route table

First preserve the transaction implementation produced by Tutorial 6, then
create a new `App.tsx` for the route table:

```sh
mv src/App.tsx src/pages/TransactionsPage.tsx
```

Create `frontend/src/App.tsx` with:

```tsx
import { Navigate, Route, Routes } from "react-router-dom";

import "./App.css";
import { AppLayout } from "./components/AppLayout";
import { CategoriesPage } from "./pages/CategoriesPage";
import { TransactionsPage } from "./pages/TransactionsPage";

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<TransactionsPage />} />
        <Route path="categories" element={<CategoriesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
```

An index route matches its parent's path, which is `/` here. The final route
redirects unknown URLs to Transactions. `replace` avoids leaving the invalid
URL as an extra browser-history entry.

`CategoriesPage` and `TransactionsPage` do not exist yet, so the TypeScript
error is expected until the following sections are complete.

## Part 3: centralise category-loading logic

Tutorial 3 added category state and a category-loading effect directly to
`App`. Create `frontend/src/hooks/useCategories.ts` with that responsibility:

```ts
import { useCallback, useEffect, useState } from "react";

import { ApiError, apiRequest } from "../api";
import type { CategoriesResponse, Category } from "../types";

function sortCategories(categories: Category[]) {
  return [...categories].sort((first, second) => {
    const typeComparison = first.category_type.localeCompare(
      second.category_type,
    );

    return typeComparison !== 0
      ? typeComparison
      : first.description.localeCompare(second.description);
  });
}

export interface CategoriesState {
  categories: Category[];
  isLoading: boolean;
  errorMessage: string | null;
  addCategory: (category: Category) => void;
}

export function useCategories(): CategoriesState {
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let shouldIgnore = false;

    async function loadCategories() {
      try {
        const response = await apiRequest<CategoriesResponse>("/categories");

        if (!shouldIgnore) {
          setCategories(response.data);
        }
      } catch (error) {
        if (!shouldIgnore) {
          setErrorMessage(
            error instanceof ApiError
              ? error.message
              : "An unexpected error occurred while loading categories.",
          );
        }
      } finally {
        if (!shouldIgnore) {
          setIsLoading(false);
        }
      }
    }

    void loadCategories();

    return () => {
      shouldIgnore = true;
    };
  }, []);

  const addCategory = useCallback((category: Category) => {
    setCategories((currentCategories) =>
      sortCategories([...currentCategories, category]),
    );
  }, []);

  return { categories, isLoading, errorMessage, addCategory };
}
```

The hook makes a defensive copy before sorting because React state must not be
mutated. `addCategory` uses the category returned by the successful POST, so
the UI gets the real database ID and backend-normalised description.

### Move the transaction feature into its page

You preserved the Tutorial 6 implementation as `TransactionsPage.tsx` before
creating the route table. Now make these focused edits to that file:

1. Change local imports such as `./api`, `./types`, and `./components/...` to
   `../api`, `../types`, and `../components/...`.
2. Remove the `./App.css` import; the route-table `App.tsx` imports it once.
3. Rename `function App()` to `export function TransactionsPage()` and remove
   `export default App`.
4. Replace the outer `<main className="app-shell">...</main>` with a fragment
   `<>...</>`, because `AppLayout` now owns the page's `<main>` landmark.
5. Remove the three category `useState` calls and the category-loading
   `useEffect` from Tutorial 3.
6. Add the hook import and destructure it inside the page:

```tsx
import { useCategories } from "../hooks/useCategories";

// Inside TransactionsPage:
const {
  categories,
  isLoading: areCategoriesLoading,
  errorMessage: categoriesError,
} = useCategories();
```

7. Remove `CategoriesResponse` and `Category` from the `../types` import; the
   hook now uses those types. Keep the transaction-related types.
8. Remove the `Personal finance` eyebrow from the page header because the
   shared layout now renders it once.

Keep all transaction loading, filters, pagination, create/edit state, PATCH,
DELETE, and confirmation behaviour from Tutorials 5 and 6 unchanged. The
existing category-loading JSX also stays unchanged because the aliases above
use its existing names.

The page header should still contain:

```tsx
<header className="page-header">
  <h1>Transactions</h1>
  <p className="page-introduction">
    Your most recent income and spending, newest first.
  </p>
</header>
```

### Link the empty-category state to its solution

In `frontend/src/components/TransactionForm.tsx`, import `Link`:

```tsx
import { Link } from "react-router-dom";
```

Replace its no-categories paragraph with:

```tsx
<p>
  You need to create a category before adding a transaction.{" "}
  <Link to="/categories">Create a category</Link>.
</p>
```

The form supports both create and edit modes after Tutorial 6. Keep that
behaviour unchanged; only replace the empty-category message. A link is better
than a button here because the action navigates to another URL.

## Part 4: build category management

The category API accepts this JSON and returns the saved category inside
`data`:

```json
{
  "description": "Salary",
  "category_type": "income"
}
```

There are intentionally no edit or delete controls. The current backend treats
categories as stable reference data and exposes only GET and POST endpoints.

### Add the single-category response type

In `frontend/src/types.ts`, add:

```ts
export interface CategoryResponse {
  data: Category;
}
```

### Create the controlled category form

Create `frontend/src/components/CategoryForm.tsx`:

```tsx
import { useState, type FormEvent } from "react";

import { apiRequest } from "../api";
import type {
  Category,
  CategoryResponse,
  CategoryType,
} from "../types";

interface CategoryFormProps {
  onCreated: (category: Category) => void;
}

export function CategoryForm({ onCreated }: CategoryFormProps) {
  const [description, setDescription] = useState("");
  const [categoryType, setCategoryType] =
    useState<CategoryType>("spending");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await apiRequest<CategoryResponse>("/categories", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          description,
          category_type: categoryType,
        }),
      });

      onCreated(response.data);
      setDescription("");
      setCategoryType("spending");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Could not create the category.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="category-form-panel" aria-labelledby="category-form-heading">
      <h2 id="category-form-heading">Add a category</h2>

      <form className="category-form" onSubmit={handleSubmit}>
        <label htmlFor="category-description">Description</label>
        <input
          id="category-description"
          name="description"
          type="text"
          maxLength={100}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          required
        />

        <label htmlFor="category-type">Type</label>
        <select
          id="category-type"
          name="category_type"
          value={categoryType}
          onChange={(event) =>
            setCategoryType(event.target.value as CategoryType)
          }
        >
          <option value="income">Income</option>
          <option value="spending">Spending</option>
        </select>

        {errorMessage !== null && <p role="alert">{errorMessage}</p>}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : "Add category"}
        </button>
      </form>
    </section>
  );
}
```

The browser enforces the obvious required and length constraints. Flask remains
the authority for business validation and duplicate detection. `apiRequest`
turns its `400` or `409` JSON error into an `Error`, and the form displays that
message without clearing the learner's input.

### Compose the Categories page

Create `frontend/src/pages/CategoriesPage.tsx`:

```tsx
import { CategoryForm } from "../components/CategoryForm";
import { useCategories } from "../hooks/useCategories";
import type { Category, CategoryType } from "../types";

interface CategoryGroupProps {
  categories: Category[];
  type: CategoryType;
}

function CategoryGroup({ categories, type }: CategoryGroupProps) {
  const title = type === "income" ? "Income categories" : "Spending categories";
  const matchingCategories = categories.filter(
    (category) => category.category_type === type,
  );

  return (
    <section className="category-group" aria-labelledby={`${type}-heading`}>
      <h2 id={`${type}-heading`}>{title}</h2>
      {matchingCategories.length === 0 ? (
        <p>No {type} categories yet.</p>
      ) : (
        <ul>
          {matchingCategories.map((category) => (
            <li key={category.id}>{category.description}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function CategoriesPage() {
  const { categories, isLoading, errorMessage, addCategory } = useCategories();

  return (
    <>
      <header className="page-header">
        <h1>Categories</h1>
        <p className="page-introduction">
          Organise transactions as income or spending.
        </p>
      </header>

      {isLoading && <p role="status">Loading categories…</p>}
      {!isLoading && errorMessage !== null && (
        <p role="alert">{errorMessage}</p>
      )}
      {!isLoading && errorMessage === null && (
        <>
          <CategoryForm onCreated={addCategory} />
          <div className="category-groups">
            <CategoryGroup categories={categories} type="income" />
            <CategoryGroup categories={categories} type="spending" />
          </div>
        </>
      )}
    </>
  );
}
```

Filtering a small category array in the browser keeps this component clear.
Transactions remain filtered by the backend because that collection can grow
and is paginated. The form appears after the initial GET completes, preventing
a very fast POST result from being overwritten by an older list response.

### Add a small amount of layout styling

Add these rules to `frontend/src/App.css`. They are a starting point rather
than a design-system requirement:

```css
.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 2rem;
}

.site-navigation {
  display: flex;
  gap: 0.5rem;
}

.site-navigation__link {
  padding: 0.5rem 0.75rem;
  border-radius: 0.4rem;
  color: inherit;
  text-decoration: none;
}

.site-navigation__link:hover,
.site-navigation__link.is-active {
  background: #e8eef7;
}

.category-form-panel,
.category-group {
  padding: 1rem;
  border: 1px solid #d8dee9;
  border-radius: 0.5rem;
}

.category-form {
  display: grid;
  gap: 0.75rem;
}

.category-groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}
```

## Part 5: verify the complete workflow manually

Run Flask on port 5001, then start the frontend in another terminal:

```sh
cd ~/finance-app/frontend
npm run dev
```

Open the Vite URL and check this story:

1. Transactions appears at `/` and its navigation link is active.
2. Select Categories; the URL becomes `/categories` without a page reload.
3. Income and spending categories appear under separate headings.
4. Create a spending category named `Utilities`.
5. It appears in the spending group using the response from Flask.
6. Submit `Utilities` again. The backend's duplicate message appears and the
   existing item is not duplicated.
7. Return to Transactions and open the Category selector. `Utilities` is
   available because the newly mounted page fetched categories again.
8. Use Back and Forward and confirm that the matching screen and active link
   follow the URL.

If your database has no categories, Transactions should show the empty-state
link. Follow `Create a category`, add one, return, and confirm that the form is
now available.

Refreshing `/categories` requires the production web server eventually to
serve `index.html` for unknown frontend paths. Vite already supplies this
fallback during development; deployment configuration is outside this lesson.

## Part 6: extend the automated tests

The tests render `App` directly, so they now need a router. In
`frontend/src/App.test.tsx`, add these imports:

```tsx
import { MemoryRouter } from "react-router-dom";
import { render, screen, within } from "@testing-library/react";
```

Keep `render` and `screen` only once if they are already imported. Add this
helper above `describe("App", ...)`:

```tsx
function renderApp(initialEntries = ["/"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <App />
    </MemoryRouter>,
  );
}
```

Replace each existing `render(<App />)` with `renderApp()`. `MemoryRouter`
stores history in memory and lets a test start at a chosen route.

### Extend the default category fixtures

Add this to `frontend/src/test/fixtures.ts`:

```ts
export const salaryCategory: Category = {
  id: 1,
  description: "Salary",
  category_type: "income",
};
```

Import it in `src/test/handlers.ts`, then change the existing categories GET
response to:

```ts
http.get("*/api/categories", () => {
  return HttpResponse.json({
    data: [salaryCategory, groceriesCategory],
  });
}),
```

### Guided example: route directly to category groups

Add this test inside the existing `describe` block:

```tsx
it("routes directly to grouped categories", async () => {
  renderApp(["/categories"]);

  expect(
    screen.getByRole("heading", { level: 1, name: "Categories" }),
  ).toBeInTheDocument();

  const incomeGroup = await screen.findByRole("region", {
    name: "Income categories",
  });
  const spendingGroup = screen.getByRole("region", {
    name: "Spending categories",
  });

  expect(within(incomeGroup).getByText("Salary")).toBeInTheDocument();
  expect(within(spendingGroup).getByText("Groceries")).toBeInTheDocument();
});
```

The `initialEntries` argument represents entering a bookmarked URL. `within`
limits a query to one category group, proving the item is under the correct
heading rather than merely somewhere on the page.

Add one more small routing test for the transaction form's empty state:

```tsx
it("links the empty category state to category management", async () => {
  const user = userEvent.setup();

  server.use(
    http.get("*/api/categories", () => {
      return HttpResponse.json({ data: [] });
    }),
  );

  renderApp();

  await user.click(
    await screen.findByRole("link", { name: "Create a category" }),
  );

  expect(
    screen.getByRole("heading", { level: 1, name: "Categories" }),
  ).toBeInTheDocument();
});
```

This uses the call to action as a person would. It tests the empty API response,
accessible link name, and destination together.

## Part 7: your exercise

Spend about 15 minutes testing category creation and navigation before reading
the reference solution.

### Exercise A: create, return, and reuse a category

Write a test named `makes a new category available after returning to transactions`:

1. Create a mutable categories array containing the two fixture categories.
2. Override both GET and POST `/api/categories` for this test.
3. Have GET return the current array.
4. Have POST assert the exact request JSON, add a saved `Utilities` category to
   the array, and return it with status 201.
5. Start at `/categories`, fill the form, and submit it.
6. Assert that `Utilities` appears in the spending group.
7. Navigate through the Transactions link.
8. Find the transaction form's Category selector and prove it contains a
   `Utilities (spending)` option.

The array in the handler represents the backend database for this one test. It
lets the second GET observe what the POST saved.

### Exercise B: display a duplicate error

Write a test named `displays the backend error for a duplicate category`:

1. Override POST `/api/categories` with status 409 and the backend's exact
   error JSON.
2. Start at `/categories` and wait for its form.
3. Enter `Groceries`, submit, and assert the alert text.

Before viewing the solution, run:

```sh
npm test -- src/App.test.tsx
```

## Part 8: reference solution

Add these imports if the test file does not already have them:

```tsx
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { groceriesCategory, salaryCategory } from "./test/fixtures";
import { server } from "./test/server";
import type { Category } from "./types";
```

### Creation and return solution

```tsx
it("makes a new category available after returning to transactions", async () => {
  const user = userEvent.setup();
  const utilitiesCategory: Category = {
    id: 3,
    description: "Utilities",
    category_type: "spending",
  };
  const savedCategories = [salaryCategory, groceriesCategory];

  server.use(
    http.get("*/api/categories", () => {
      return HttpResponse.json({ data: savedCategories });
    }),
    http.post("*/api/categories", async ({ request }) => {
      expect(await request.json()).toEqual({
        description: "Utilities",
        category_type: "spending",
      });
      savedCategories.push(utilitiesCategory);
      return HttpResponse.json({ data: utilitiesCategory }, { status: 201 });
    }),
  );

  renderApp(["/categories"]);
  await screen.findByRole("heading", { name: "Add a category" });

  await user.type(screen.getByLabelText("Description"), "Utilities");
  await user.selectOptions(screen.getByLabelText("Type"), "spending");
  await user.click(screen.getByRole("button", { name: "Add category" }));

  expect(await screen.findByText("Utilities")).toBeInTheDocument();

  await user.click(screen.getByRole("link", { name: "Transactions" }));

  const categorySelect = await screen.findByLabelText("Category");
  expect(
    within(categorySelect).getByRole("option", {
      name: "Utilities (spending)",
    }),
  ).toBeInTheDocument();
});
```

The navigation unmounts `CategoriesPage` and mounts `TransactionsPage`. Its new
`useCategories` instance performs GET `/api/categories`, which reads the
updated handler array. This test protects the refresh behaviour rather than
depending on shared client state.

### Duplicate-error solution

```tsx
it("displays the backend error for a duplicate category", async () => {
  const user = userEvent.setup();

  server.use(
    http.post("*/api/categories", () => {
      return HttpResponse.json(
        { error: "A category with that description already exists." },
        { status: 409 },
      );
    }),
  );

  renderApp(["/categories"]);
  await screen.findByRole("heading", { name: "Add a category" });

  await user.type(screen.getByLabelText("Description"), "Groceries");
  await user.click(screen.getByRole("button", { name: "Add category" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "A category with that description already exists.",
  );
});
```

This assertion checks the message a caller relies on rather than merely
checking that some error occurred.

## Part 9: run every check

From `frontend`:

```sh
npm test
npm run lint
npm run build
```

All earlier transaction tests should still pass after replacing their renders
with `renderApp()`. If a test reports that `useRoutes()` may only be used inside
a router, one direct `render(<App />)` remains. If MSW reports an unexpected
categories request, make sure the GET handler is present in that test or in the
default handlers.

## Commit the milestone

Inspect the changes before committing:

```sh
cd ~/finance-app
git status --short
git diff
git add frontend/package.json frontend/package-lock.json frontend/src \
  docs/frontend/07-category-management-routing-tutorial.md
git commit -m "Add category management and frontend routing"
git push -u origin add-category-management
```

The application now covers every endpoint in the current backend: categories
can be listed and created, and transactions can be listed, filtered, created,
edited, and deleted. Routing was introduced only when there were real pages to
navigate between, and category state remains simple and server-led.
