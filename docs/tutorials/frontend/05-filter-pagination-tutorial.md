# Tutorial 5: filter and paginate transactions

The transaction list now loads from the API, the creation form can add a
transaction, and automated tests protect those behaviours. In this tutorial
you will make a long list easier to explore by adding filters and page
controls.

The browser will send requests such as:

```text
GET /api/transactions
    ?type=spending
    &category_id=2
    &start_date=2026-08-01
    &end_date=2026-08-31
    &search=market
    &page=1
    &per_page=10
```

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Understand draft and applied state | 10 minutes |
| Build the filter form | 15 minutes |
| Request filtered pages | 15 minutes |
| Add pagination controls | 10 minutes |
| Test, check, and commit | 10 minutes |

## What we are building

The transaction page will gain five filters:

| Control | API query parameter | Meaning |
| --- | --- | --- |
| Type | `type` | `income` or `spending` |
| Category | `category_id` | One exact category ID |
| From | `start_date` | Earliest date, inclusive |
| To | `end_date` | Latest date, inclusive |
| Description | `search` | Case-insensitive text search |

All filters are optional. The API combines supplied filters with AND logic. A
search for spending in the Groceries category during August must satisfy all
three conditions.

The form has an explicit **Apply filters** button. Typing does not immediately
request data. This distinction gives us two kinds of state:

```text
draft filters                  applied filters
what the controls show  --Apply-->  what the current request uses
```

This is easier to reason about than making a request after every keystroke. A
debounced search would also introduce timers and effect cleanup before those
concepts solve an important problem.

Below the results, **Previous** and **Next** will request another server page.
The API, rather than React, remains responsible for filtering, ordering,
counting, and selecting the records on that page.

## Before you start

Complete Tutorial 4 and make sure its tests pass. The backend Tutorial 5 must
also be complete because this frontend relies on its query parameters and
pagination response.

Create a branch:

```sh
cd ~/finance-app
git switch -c add-frontend-filters-pagination
cd frontend
npm test
```

Start MariaDB, Flask on port 5001, and Vite when you are ready for the manual
checks. Automated frontend tests will continue to use MSW instead of the real
backend.

## Step 1: describe editable filter values

Open `frontend/src/types.ts`. Add this interface after `CategoryType` and the
existing response types:

```ts
export interface TransactionFilterValues {
  type: CategoryType | "";
  categoryId: string;
  startDate: string;
  endDate: string;
  search: string;
}
```

The property names are convenient TypeScript names for the form. Later we will
translate them to the backend's snake_case query names.

Every value is a string while it belongs to an HTML control. In particular,
`categoryId` is a string even though a saved `Transaction` has a numeric
`category_id`. An empty string naturally represents “no filter” in a select,
date input, or text input.

The type field is narrower than a general string:

```ts
CategoryType | ""
```

It can contain only `"income"`, `"spending"`, or the empty choice.

## Step 2: build a controlled filter form

Create `frontend/src/components/TransactionFilters.tsx`:

```tsx
import type { FormEvent } from "react";

import type {
  Category,
  TransactionFilterValues,
} from "../types";

interface TransactionFiltersProps {
  categories: Category[];
  filters: TransactionFilterValues;
  onChange: (filters: TransactionFilterValues) => void;
  onApply: () => void;
  onClear: () => void;
}

export function TransactionFilters({
  categories,
  filters,
  onChange,
  onApply,
  onClear,
}: TransactionFiltersProps) {
  function updateFilter<Key extends keyof TransactionFilterValues>(
    name: Key,
    value: TransactionFilterValues[Key],
  ) {
    onChange({ ...filters, [name]: value });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onApply();
  }

  return (
    <section className="filters-panel" aria-labelledby="filters-heading">
      <h2 id="filters-heading">Filter transactions</h2>

      <form className="filters-form" onSubmit={handleSubmit}>
        <label>
          Type
          <select
            value={filters.type}
            onChange={(event) =>
              updateFilter(
                "type",
                event.target.value as TransactionFilterValues["type"],
              )
            }
          >
            <option value="">All types</option>
            <option value="income">Income</option>
            <option value="spending">Spending</option>
          </select>
        </label>

        <label>
          Filter category
          <select
            value={filters.categoryId}
            onChange={(event) =>
              updateFilter("categoryId", event.target.value)
            }
          >
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.description}
              </option>
            ))}
          </select>
        </label>

        <label>
          From
          <input
            type="date"
            value={filters.startDate}
            onChange={(event) =>
              updateFilter("startDate", event.target.value)
            }
          />
        </label>

        <label>
          To
          <input
            type="date"
            value={filters.endDate}
            onChange={(event) =>
              updateFilter("endDate", event.target.value)
            }
          />
        </label>

        <label>
          Search descriptions
          <input
            type="search"
            value={filters.search}
            onChange={(event) => updateFilter("search", event.target.value)}
            placeholder="For example, market"
          />
        </label>

        <div className="filter-actions">
          <button type="submit">Apply filters</button>
          <button type="button" onClick={onClear}>
            Clear filters
          </button>
        </div>
      </form>
    </section>
  );
}
```

This is a **controlled component**. It does not own the values shown in its
controls. `App` passes the current object in `filters`; each change passes a new
object back through `onChange`.

The spread operation preserves the fields that did not change:

```ts
onChange({ ...filters, [name]: value });
```

The generic `Key` links the property name to the correct property value type.
The type select still needs one assertion because the DOM exposes any selected
option as a general `string`; we know its options restrict the runtime value.

The buttons have different types deliberately. The Apply button submits the
form, including when Enter is pressed. The Clear button must not accidentally
submit before clearing.

## Step 3: turn filter state into a query string

At the top of `frontend/src/App.tsx`, add the component import:

```tsx
import { TransactionFilters } from "./components/TransactionFilters";
```

Keep the existing imports for `TransactionForm` and `TransactionList`. Add
`TransactionFilterValues` to the existing `import type { ... } from
"./types"` list rather than creating a second import from the same module.

Above `App`, add an empty filter object, a page size, and a query builder:

```ts
const EMPTY_FILTERS: TransactionFilterValues = {
  type: "",
  categoryId: "",
  startDate: "",
  endDate: "",
  search: "",
};

const PER_PAGE = 10;

function buildTransactionQuery(
  filters: TransactionFilterValues,
  page: number,
) {
  const parameters = new URLSearchParams();

  if (filters.type) parameters.set("type", filters.type);
  if (filters.categoryId) {
    parameters.set("category_id", filters.categoryId);
  }
  if (filters.startDate) parameters.set("start_date", filters.startDate);
  if (filters.endDate) parameters.set("end_date", filters.endDate);
  if (filters.search) parameters.set("search", filters.search);

  parameters.set("page", String(page));
  parameters.set("per_page", String(PER_PAGE));

  return parameters.toString();
}
```

`URLSearchParams` performs the necessary URL encoding. A search such as
`coffee & cake` becomes safe query text; manually joining strings would easily
produce a broken or ambiguous URL.

Empty filters are omitted instead of sending values such as `search=`. This is
important because the backend correctly rejects a blank supplied search.
`page` and `per_page` are always included, making the frontend's paging choice
explicit.

## Step 4: keep draft and applied state in `App`

Inside `App`, add this state beside the existing transaction state:

```tsx
const [draftFilters, setDraftFilters] =
  useState<TransactionFilterValues>(EMPTY_FILTERS);
const [appliedFilters, setAppliedFilters] =
  useState<TransactionFilterValues>(EMPTY_FILTERS);
const [page, setPage] = useState(1);
const [refreshKey, setRefreshKey] = useState(0);
```

Then derive the query string during rendering:

```tsx
const transactionQuery = buildTransactionQuery(appliedFilters, page);
```

Replace the transaction-loading effect's request with the query-aware path:

```tsx
useEffect(() => {
  let shouldIgnore = false;

  async function loadTransactions() {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await apiRequest<TransactionsResponse>(
        `/transactions?${transactionQuery}`,
      );

      if (!shouldIgnore) {
        setTransactions(response.data);
        setPagination(response.pagination);
      }
    } catch (error) {
      if (!shouldIgnore) {
        const message =
          error instanceof ApiError
            ? error.message
            : "An unexpected error occurred while loading transactions.";
        setErrorMessage(message);
      }
    } finally {
      if (!shouldIgnore) {
        setIsLoading(false);
      }
    }
  }

  void loadTransactions();

  return () => {
    shouldIgnore = true;
  };
}, [transactionQuery, refreshKey]);
```

The effect now synchronizes whenever the applied query or `refreshKey`
changes. A query string is a primitive string. Rebuilding the same string on a
render does not retrigger the effect because React compares dependencies by
value.

Avoid writing this instead:

```tsx
// Do not construct a new object in the dependency array.
useEffect(() => {
  // ...
}, [{ filters: appliedFilters, page }]);
```

That object is new on every render, even if its contents are equal, so the
effect would request data after every render. The request updates state, which
causes another render and can produce a request loop. Deriving one stable
primitive dependency also keeps the exact URL logic in one place.

Add these handlers inside `App`:

```tsx
function handleApplyFilters() {
  setAppliedFilters({
    ...draftFilters,
    search: draftFilters.search.trim(),
  });
  setPage(1);
}

function handleClearFilters() {
  setDraftFilters(EMPTY_FILTERS);
  setAppliedFilters(EMPTY_FILTERS);
  setPage(1);
}

function handleTransactionCreated() {
  setPage(1);
  setRefreshKey((currentKey) => currentKey + 1);
}
```

Applying filters copies the current draft and resets the page. Without the
reset, somebody on page 4 could apply a narrow filter with only one page and
see an empty result. Clearing updates both objects, so the controls and the
request return to their initial state together.

The creation callback no longer calls the original unfiltered loader from
Tutorial 3. It does not guess where the saved transaction belongs or whether it
matches the active filters. Incrementing `refreshKey` asks this query-aware
effect for the authoritative first page.

Render the filter component after the creation form and before the transaction
panel:

```tsx
<TransactionFilters
  categories={categories}
  filters={draftFilters}
  onChange={setDraftFilters}
  onApply={handleApplyFilters}
  onClear={handleClearFilters}
/>
```

Changing `draftFilters` rerenders the controls but does not change
`transactionQuery`, so it does not run the fetching effect. Applying or
clearing changes `appliedFilters`, which changes the query and starts a request.

## Step 5: add the result count and page controls

In the transaction panel heading, replace the existing count with a label that
describes the filtered result:

```tsx
{pagination !== null && (
  <span className="transaction-count">
    {pagination.total_items === 1
      ? "1 matching transaction"
      : `${pagination.total_items} matching transactions`}
  </span>
)}
```

`total_items` is the number of records matching the applied filters across all
pages. It is not merely `transactions.length`, which can never exceed 10 in
this frontend.

After the list and empty-state JSX, still inside the transaction panel, add:

```tsx
{!isLoading && errorMessage === null && pagination !== null && (
  <nav className="pagination" aria-label="Transaction pages">
    <button
      type="button"
      disabled={!pagination.has_previous}
      onClick={() => setPage((currentPage) => currentPage - 1)}
    >
      Previous
    </button>

    <span>
      Page {pagination.page} of {Math.max(pagination.total_pages, 1)}
    </span>

    <button
      type="button"
      disabled={!pagination.has_next}
      onClick={() => setPage((currentPage) => currentPage + 1)}
    >
      Next
    </button>
  </nav>
)}
```

The API tells the UI whether a neighbouring page exists. This is safer than
guessing from the number of rows. The functional updater receives the latest
page value, so two pieces of code cannot accidentally calculate from an old
render.

An empty result reports zero total pages. The UI displays `Page 1 of 1` rather
than the confusing `Page 1 of 0`, while both buttons remain disabled according
to the API metadata.

## Step 6: review the completed `App`

Your `frontend/src/App.tsx` should now have this overall shape. The full version
below includes the category-loading code from Tutorial 3 so you can compare
your result exactly:

```tsx
import { useEffect, useState } from "react";

import { ApiError, apiRequest } from "./api";
import { TransactionFilters } from "./components/TransactionFilters";
import { TransactionForm } from "./components/TransactionForm";
import { TransactionList } from "./components/TransactionList";
import type {
  CategoriesResponse,
  Category,
  Pagination,
  Transaction,
  TransactionFilterValues,
  TransactionsResponse,
} from "./types";
import "./App.css";

const EMPTY_FILTERS: TransactionFilterValues = {
  type: "",
  categoryId: "",
  startDate: "",
  endDate: "",
  search: "",
};

const PER_PAGE = 10;

function buildTransactionQuery(
  filters: TransactionFilterValues,
  page: number,
) {
  const parameters = new URLSearchParams();

  if (filters.type) parameters.set("type", filters.type);
  if (filters.categoryId) {
    parameters.set("category_id", filters.categoryId);
  }
  if (filters.startDate) parameters.set("start_date", filters.startDate);
  if (filters.endDate) parameters.set("end_date", filters.endDate);
  if (filters.search) parameters.set("search", filters.search);

  parameters.set("page", String(page));
  parameters.set("per_page", String(PER_PAGE));
  return parameters.toString();
}

function App() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [areCategoriesLoading, setAreCategoriesLoading] = useState(true);
  const [draftFilters, setDraftFilters] =
    useState<TransactionFilterValues>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] =
    useState<TransactionFilterValues>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);

  const transactionQuery = buildTransactionQuery(appliedFilters, page);

  useEffect(() => {
    let shouldIgnore = false;

    async function loadTransactions() {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const response = await apiRequest<TransactionsResponse>(
          `/transactions?${transactionQuery}`,
        );

        if (!shouldIgnore) {
          setTransactions(response.data);
          setPagination(response.pagination);
        }
      } catch (error) {
        if (!shouldIgnore) {
          setErrorMessage(
            error instanceof ApiError
              ? error.message
              : "An unexpected error occurred while loading transactions.",
          );
        }
      } finally {
        if (!shouldIgnore) setIsLoading(false);
      }
    }

    void loadTransactions();

    return () => {
      shouldIgnore = true;
    };
  }, [transactionQuery, refreshKey]);

  useEffect(() => {
    async function loadCategories() {
      try {
        const response = await apiRequest<CategoriesResponse>("/categories");
        setCategories(response.data);
      } catch (error) {
        setCategoriesError(
          error instanceof Error ? error.message : "Could not load categories.",
        );
      } finally {
        setAreCategoriesLoading(false);
      }
    }

    void loadCategories();
  }, []);

  function handleApplyFilters() {
    setAppliedFilters({
      ...draftFilters,
      search: draftFilters.search.trim(),
    });
    setPage(1);
  }

  function handleClearFilters() {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
  }

  function handleTransactionCreated() {
    setPage(1);
    setRefreshKey((currentKey) => currentKey + 1);
  }

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Personal finance</p>
        <h1>Transactions</h1>
        <p className="page-introduction">
          Your most recent income and spending, newest first.
        </p>
      </header>

      {areCategoriesLoading && <p>Loading categories…</p>}
      {categoriesError !== null && <p role="alert">{categoriesError}</p>}
      {!areCategoriesLoading && categoriesError === null && (
        <TransactionForm
          categories={categories}
          onCreated={handleTransactionCreated}
        />
      )}

      <TransactionFilters
        categories={categories}
        filters={draftFilters}
        onChange={setDraftFilters}
        onApply={handleApplyFilters}
        onClear={handleClearFilters}
      />

      <section className="transactions-panel" aria-labelledby="transactions-heading">
        <div className="panel-heading">
          <h2 id="transactions-heading">Transaction history</h2>
          {pagination !== null && (
            <span className="transaction-count">
              {pagination.total_items === 1
                ? "1 matching transaction"
                : `${pagination.total_items} matching transactions`}
            </span>
          )}
        </div>

        {isLoading && (
          <p className="status-message" role="status">
            Loading transactions…
          </p>
        )}

        {!isLoading && errorMessage !== null && (
          <p className="status-message status-message--error" role="alert">
            {errorMessage}
          </p>
        )}

        {!isLoading && errorMessage === null && transactions.length === 0 && (
          <p className="status-message">No transactions yet.</p>
        )}

        {!isLoading && errorMessage === null && transactions.length > 0 && (
          <TransactionList transactions={transactions} />
        )}

        {!isLoading && errorMessage === null && pagination !== null && (
          <nav className="pagination" aria-label="Transaction pages">
            <button
              type="button"
              disabled={!pagination.has_previous}
              onClick={() => setPage((currentPage) => currentPage - 1)}
            >
              Previous
            </button>
            <span>
              Page {pagination.page} of {Math.max(pagination.total_pages, 1)}
            </span>
            <button
              type="button"
              disabled={!pagination.has_next}
              onClick={() => setPage((currentPage) => currentPage + 1)}
            >
              Next
            </button>
          </nav>
        )}
      </section>
    </main>
  );
}

export default App;
```

## Step 7: add a small amount of styling

Append these rules to `frontend/src/App.css`:

```css
.filters-panel {
  margin: 2rem 0;
  padding: 1.5rem;
  border: 1px solid #dbe2ea;
  border-radius: 1rem;
  background: #ffffff;
}

.filters-panel h2 {
  margin-top: 0;
}

.filters-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: 1rem;
  align-items: end;
}

.filters-form label {
  display: grid;
  gap: 0.35rem;
  font-weight: 600;
}

.filters-form input,
.filters-form select,
.filter-actions button,
.pagination button {
  min-height: 2.5rem;
  padding: 0.5rem 0.7rem;
  font: inherit;
}

.filter-actions,
.pagination {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.pagination {
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e8edf2;
}
```

The responsive grid lets controls wrap as the screen narrows. Native labels,
inputs, selects, and buttons remain keyboard accessible without extra event
handling.

## Step 8: test the query parameters

Open `frontend/src/App.test.tsx`. Add `waitFor` and `userEvent` to the imports
if they are not already present:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
```

The new tests use both fixtures, so make sure the fixture import contains:

```tsx
import { groceriesCategory, weeklyShop } from "./test/fixtures";
```

Add this test inside the existing `describe("App", ...)` block:

```tsx
it("applies all transaction filters to the request", async () => {
  const user = userEvent.setup();
  const requestedUrls: URL[] = [];

  server.use(
    http.get("*/api/transactions", ({ request }) => {
      requestedUrls.push(new URL(request.url));

      return HttpResponse.json({
        data: [weeklyShop],
        pagination: {
          page: 1,
          per_page: 10,
          total_items: 1,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
      });
    }),
  );

  render(<App />);
  await screen.findByText("Weekly shop");

  await user.selectOptions(screen.getByLabelText("Type"), "spending");
  await user.selectOptions(screen.getByLabelText("Filter category"), "2");
  await user.type(screen.getByLabelText("From"), "2026-08-01");
  await user.type(screen.getByLabelText("To"), "2026-08-31");
  await user.type(screen.getByLabelText("Search descriptions"), "market");
  await user.click(screen.getByRole("button", { name: "Apply filters" }));

  await waitFor(() => {
    expect(requestedUrls.at(-1)?.searchParams.get("search")).toBe("market");
  });

  const parameters = requestedUrls.at(-1)!.searchParams;
  expect(parameters.get("type")).toBe("spending");
  expect(parameters.get("category_id")).toBe("2");
  expect(parameters.get("start_date")).toBe("2026-08-01");
  expect(parameters.get("end_date")).toBe("2026-08-31");
  expect(parameters.get("search")).toBe("market");
  expect(parameters.get("page")).toBe("1");
  expect(parameters.get("per_page")).toBe("10");
});
```

This test uses the controls as a person would, then inspects the request at the
network boundary. It verifies both the camelCase-to-snake_case mapping and the
values without testing private component state.

Why inspect the last URL instead of the first? Rendering the page makes an
initial unfiltered request. Clicking Apply makes the request under test.

The non-null assertion in `requestedUrls.at(-1)!` is safe after `waitFor` has
proved that the matching request exists.

## Step 9: pagination test exercise

Try this test before looking at the reference solution:

> Write a test named `moves between transaction pages`. Make the mock endpoint
> return `Weekly shop` for page 1 and a transaction named `Second page item`
> for page 2. On the first page, prove Previous is disabled and Next is
> enabled. Click Next, check that the request contains `page=2`, find the
> second-page item, and prove the enabled states have reversed.

Use the request URL to decide which mock response to return. Do not mock the
button handler or access React state.

### Reference solution

Add this test to `frontend/src/App.test.tsx`:

```tsx
it("moves between transaction pages", async () => {
  const user = userEvent.setup();
  const requestedPages: string[] = [];

  server.use(
    http.get("*/api/transactions", ({ request }) => {
      const requestedPage = new URL(request.url).searchParams.get("page") ?? "1";
      requestedPages.push(requestedPage);
      const isSecondPage = requestedPage === "2";

      return HttpResponse.json({
        data: [
          isSecondPage
            ? { ...weeklyShop, id: 11, description: "Second page item" }
            : weeklyShop,
        ],
        pagination: {
          page: Number(requestedPage),
          per_page: 10,
          total_items: 2,
          total_pages: 2,
          has_next: !isSecondPage,
          has_previous: isSecondPage,
        },
      });
    }),
  );

  render(<App />);
  await screen.findByText("Weekly shop");

  const previous = screen.getByRole("button", { name: "Previous" });
  const next = screen.getByRole("button", { name: "Next" });
  expect(previous).toBeDisabled();
  expect(next).toBeEnabled();
  expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();

  await user.click(next);

  expect(await screen.findByText("Second page item")).toBeInTheDocument();
  expect(requestedPages.at(-1)).toBe("2");
  expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
  expect(previous).toBeEnabled();
  expect(next).toBeDisabled();
});
```

Notice that the test's mock behaves like the backend: its data and metadata
both depend on `page`. Returning page 1 metadata with page 2 records could let
an impossible UI state hide a bug.

## Step 10: update the creation test metadata

Tutorial 4's creation test already makes its mock GET reflect the successful
POST. The frontend now explicitly asks for 10 rows, so change `per_page: 20` to
`per_page: 10` in that test's GET override. Keep its saved transaction, boolean,
request-body, and visible-result assertions unchanged.

The application does not currently reject mismatched mock metadata, so the old
value might not fail a test. Keeping fixtures faithful to real requests avoids
building confidence from an impossible API response.

## Step 11: manually verify the feature

With Flask and Vite running, open the frontend and the browser's Network panel.
Work through these checks:

1. The first transaction request includes `page=1&per_page=10`.
2. Change several fields without applying. Confirm no new transaction request
   is made.
3. Apply the filters. Confirm one request contains the exact selected values.
4. Confirm the result count reflects all matching records, not just this page.
5. If there is another page, click Next and confirm only `page` changes.
6. Apply a different filter while on a later page and confirm it requests page
   1.
7. Clear the filters and confirm the controls empty and the unfiltered first
   page returns.
8. Search for text containing a space or `&`; inspect its encoded request and
   confirm the backend receives it correctly.
9. Choose a date range with no matches. Confirm the empty message appears and
   both page buttons are disabled.

Also create a transaction while filters are active. The app should return to
page 1 and refetch. The new record appears only if it matches the applied
filters, which is the correct server-authoritative behaviour.

## Common problems

### A request happens after every keystroke

Check that `transactionQuery` is built from `appliedFilters`, not
`draftFilters`. Input changes should update only the draft object.

### Requests repeat forever

Check the effect dependency array. Depend on `transactionQuery` and
`refreshKey`, not on an object or `new URLSearchParams()` created inline.

### The backend reports an unknown query parameter

Compare the generated URL with the mapping table. The API uses `category_id`,
`start_date`, and `end_date`, not the React property names.

### Applying a narrow filter shows an empty later page

Both Apply and Clear must call `setPage(1)`. Do not wait for a later effect to
repair the page.

### A blank search returns a 400 response

Trim the search when applying it and omit empty values in
`buildTransactionQuery`. Sending `search=` is different from not supplying the
parameter.

## Review exercises

1. Explain why draft and applied filters should not be the same state object.
2. Add a test that changes Description but proves no filtered request occurs
   until Apply is clicked.
3. Add a test that starts on page 2, applies a filter, and proves the next
   request contains `page=1`.
4. Add a test for Clear filters. Check the controls and prove the next URL
   omits all five optional parameters.
5. Explain why `pagination.total_items` is more useful than
   `transactions.length` for the heading count.

## Run all checks

Run the test suite and the existing static checks:

```sh
cd ~/finance-app/frontend
npm test
npm run lint
npm run build
```

The App test file should now contain the four tests from Tutorial 4 plus the
filter and pagination tests from this tutorial. Exact output varies, but all
six should pass.

## Commit the milestone

Inspect and commit the completed feature:

```sh
cd ~/finance-app
git status --short
git diff
git add frontend/src/App.tsx frontend/src/App.css \
  frontend/src/components/TransactionFilters.tsx frontend/src/types.ts \
  frontend/src/App.test.tsx docs/frontend/05-filter-pagination-tutorial.md
git commit -m "Add transaction filters and pagination"
```

You now have a server-backed list that composes five filters, exposes accurate
result metadata, and moves through deterministic pages. You also separated
draft form state from applied request state and learned how stable derived
values keep an effect's dependencies predictable. The next tutorial will add
editing and deletion while preserving these filtered, paginated results.
