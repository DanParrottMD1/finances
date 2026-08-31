# Tutorial 2: display the transaction history

Tutorial 1 gave us a React application that can contact the Flask API. In this
tutorial we will replace the health-check demonstration with the first useful
screen in the finance application: a read-only transaction history.

The page will request:

```text
GET /api/transactions
```

It will show a suitable interface while the request is loading, when it fails,
when there are no transactions, and when data is available. Along the way, we
will introduce React state, effects, props, conditional rendering, and rendering
a list.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Understand the data flow and define types | 10 minutes |
| Fetch transactions with an effect | 15 minutes |
| Build the transaction components | 15 minutes |
| Add formatting and styles | 15 minutes |
| Check the four interface states | 5 minutes |

## What we are building

The backend response has this shape:

```json
{
  "data": [
    {
      "id": 3,
      "amount": "1000.00",
      "transaction_date": "2026-08-03",
      "description": "Rent for August",
      "category_id": 3,
      "category": {
        "id": 3,
        "description": "Rent",
        "category_type": "spending"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_items": 1,
    "total_pages": 1,
    "has_next": false,
    "has_previous": false
  }
}
```

This tutorial displays the first page returned by the API. We will add controls
for filters and pagination in Tutorial 5.

Our component tree will be:

```text
App
└── TransactionList
    └── TransactionRow (one for each transaction)
```

`App` owns the server data because it performs the request. It passes that data
down to the list through **props**. The smaller components are concerned only
with presentation.

## Before you start

Complete Tutorial 1 and make sure both development servers are running in
separate terminals.

Start Flask:

```sh
cd ~/finance-app/backend
source .venv/bin/activate
flask --app run run --host 0.0.0.0 --port 5001
```

Start Vite:

```sh
cd ~/finance-app/frontend
npm run dev
```

The frontend `.env` file should still contain:

```text
VITE_API_BASE_URL=http://127.0.0.1:5001/api
```

Create a branch from the work completed in Tutorial 1:

```sh
cd ~/finance-app
git switch -c display-transaction-history
```

No new npm packages are needed in this tutorial.

## Step 1: describe the API data with TypeScript

Create `frontend/src/types.ts`:

```ts
export type CategoryType = "income" | "spending";

export interface Category {
  id: number;
  description: string;
  category_type: CategoryType;
}

export interface Transaction {
  id: number;
  amount: string;
  transaction_date: string;
  description: string | null;
  category_id: number;
  category: Category;
}

export interface Pagination {
  page: number;
  per_page: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface TransactionsResponse {
  data: Transaction[];
  pagination: Pagination;
}
```

An `interface` describes the fields TypeScript expects an object to have. It
does not change the response at runtime, but it lets the editor and compiler
catch mistakes such as writing `transaction.date` when the real field is named
`transaction_date`.

### Why is `amount` a string?

The backend deliberately serializes its exact decimal value as a string. JavaScript
numbers use floating-point arithmetic, which cannot represent every decimal
fraction exactly. Keep the API value as a string in the domain type. We will
convert it only when formatting it for the screen; later form tutorials will
send decimal text back to the API.

### Why can `description` be null?

A transaction description is optional in the database. `string | null` makes
the two possibilities explicit, so a component must handle a missing
description rather than accidentally trying to use it as text.

### Why define pagination before we use its controls?

The response already contains `pagination`, so our TypeScript type should
describe the entire response. In this tutorial we use `total_items`; later we
will also use the page and next/previous fields.

## Step 2: build a transaction row

Create a components directory:

```sh
cd ~/finance-app/frontend
mkdir -p src/components
```

Create `frontend/src/components/TransactionRow.tsx`:

```tsx
import type { Transaction } from "../types";

interface TransactionRowProps {
  transaction: Transaction;
}

const moneyFormatter = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
});

const dateFormatter = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
});

function formatMoney(amount: string) {
  return moneyFormatter.format(Number(amount));
}

function formatDate(isoDate: string) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return dateFormatter.format(new Date(year, month - 1, day));
}

export function TransactionRow({ transaction }: TransactionRowProps) {
  const isIncome = transaction.category.category_type === "income";

  return (
    <tr>
      <td>{formatDate(transaction.transaction_date)}</td>
      <td>
        <span className={`transaction-type transaction-type--${transaction.category.category_type}`}>
          {transaction.category.category_type}
        </span>
      </td>
      <td>{transaction.category.description}</td>
      <td>{transaction.description ?? "No description"}</td>
      <td className={`transaction-amount ${isIncome ? "transaction-amount--income" : ""}`}>
        {isIncome ? "+" : "−"}
        {formatMoney(transaction.amount)}
      </td>
    </tr>
  );
}
```

A React component is a function that returns JSX. Its name begins with a
capital letter so React can distinguish it from an HTML element.

`TransactionRowProps` describes the component's input. This component requires
exactly one prop named `transaction`, and that prop must match our `Transaction`
interface. The braces in the function parameter extract that prop:

```ts
function TransactionRow({ transaction }: TransactionRowProps)
```

The `import type` syntax tells TypeScript that `Transaction` is used only during
type checking. It does not need to be included in the browser's JavaScript.

### Formatting dates without a timezone surprise

An API date such as `2026-08-03` represents a calendar day, not a moment in a
particular timezone. Passing that string directly to `new Date()` can be
interpreted as midnight UTC and may display as the previous day in timezones
west of UTC. Splitting the fields and constructing a local date preserves the
calendar date the user entered.

### Conditional values and class names

The ternary expression:

```tsx
isIncome ? "+" : "−"
```

chooses one value based on a condition. We use the same idea to add a CSS class
to income amounts. The category type is also embedded in a class name with a
template literal, producing either `transaction-type--income` or
`transaction-type--spending`.

The nullish coalescing operator in:

```tsx
transaction.description ?? "No description"
```

uses the fallback only when the description is `null` or `undefined`.

## Step 3: render the list

Create `frontend/src/components/TransactionList.tsx`:

```tsx
import type { Transaction } from "../types";
import { TransactionRow } from "./TransactionRow";

interface TransactionListProps {
  transactions: Transaction[];
}

export function TransactionList({ transactions }: TransactionListProps) {
  return (
    <div className="transaction-table-wrapper">
      <table className="transaction-table">
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Type</th>
            <th scope="col">Category</th>
            <th scope="col">Description</th>
            <th scope="col">Amount</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((transaction) => (
            <TransactionRow key={transaction.id} transaction={transaction} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

`map` transforms every transaction into a `TransactionRow`. JSX expressions go
inside braces, so the JavaScript expression appears as:

```tsx
{transactions.map(/* ... */)}
```

Every item rendered from an array needs a stable `key`. React uses keys to
match the previous rows with the new rows when data changes. The database ID is
stable and unique, so `transaction.id` is a better key than the array position.

The `key` is for React itself. It is not included in `TransactionRowProps`; the
actual transaction is passed separately with `transaction={transaction}`.

The wrapper lets a narrow screen scroll the table horizontally rather than
forcing the entire page wider than the viewport.

## Step 4: fetch transactions in `App`

Replace `frontend/src/App.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { ApiError, apiRequest } from "./api";
import { TransactionList } from "./components/TransactionList";
import type { Pagination, Transaction, TransactionsResponse } from "./types";
import "./App.css";

function App() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let shouldIgnore = false;

    async function loadTransactions() {
      try {
        const response = await apiRequest<TransactionsResponse>("/transactions");

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

    loadTransactions();

    return () => {
      shouldIgnore = true;
    };
  }, []);

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">Personal finance</p>
        <h1>Transactions</h1>
        <p className="page-introduction">
          Your most recent income and spending, newest first.
        </p>
      </header>

      <section className="transactions-panel" aria-labelledby="transactions-heading">
        <div className="panel-heading">
          <h2 id="transactions-heading">Transaction history</h2>
          {pagination !== null && (
            <span className="transaction-count">
              {pagination.total_items} total
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
      </section>
    </main>
  );
}

export default App;
```

### State remembers values between renders

Calling `useState` creates a state value and a function that updates it:

```ts
const [transactions, setTransactions] = useState<Transaction[]>([]);
```

The generic type between angle brackets says this state is always an array of
transactions. Its initial value is an empty array. Calling `setTransactions`
stores a new value and asks React to render the component again.

The component has four independent pieces of state:

| State | Initial value | Purpose |
| --- | --- | --- |
| `transactions` | `[]` | Records returned by Flask |
| `pagination` | `null` | Metadata returned alongside the records |
| `isLoading` | `true` | Whether the initial request is unfinished |
| `errorMessage` | `null` | A user-facing failure message, if any |

An empty transaction array cannot tell us whether a request is still in
progress, failed, or successfully found no results. Keeping explicit loading
and error state lets the interface distinguish those cases.

### Effects synchronize React with an external system

Rendering should calculate JSX from existing values; it should not start a
network request. `useEffect` runs after React has committed a render, making it
the appropriate place to synchronize this component with the API.

The empty dependency array at the end:

```ts
}, []);
```

means the effect does not depend on props or state and should run when the
component is mounted. During development, React Strict Mode may deliberately
run an effect, clean it up, and run it again. This helps reveal unsafe effects.
The `shouldIgnore` cleanup prevents an old request from updating a component
after that effect has been cleaned up. Seeing two GET requests in the browser's
Network panel during development is therefore not necessarily a bug.

`apiRequest<TransactionsResponse>` tells our generic API helper what successful
JSON shape to return. TypeScript can then check `response.data` and
`response.pagination` throughout the rest of the function.

### Conditional rendering covers every state

React uses normal JavaScript expressions to decide which JSX to include. With
`condition && <Element />`, the element is rendered only when the condition is
true.

Our conditions are deliberately mutually exclusive:

```text
loading
├── yes: loading message
└── no
    ├── error: error message
    └── no error
        ├── zero transactions: empty message
        └── one or more transactions: table
```

`role="status"` lets assistive technology announce the loading update without
interrupting the user. `role="alert"` makes the failure more urgent. The table
headers use `scope="col"` so screen readers can associate them with each cell.

## Step 5: style the transaction page

Replace `frontend/src/App.css` with:

```css
#root {
  min-height: 100vh;
}

.app-shell {
  width: min(1100px, calc(100% - 2rem));
  margin: 0 auto;
  padding: 4rem 0;
}

.page-header {
  margin-bottom: 2rem;
}

.eyebrow {
  margin: 0 0 0.4rem;
  color: #2563eb;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-header h1,
.panel-heading h2 {
  margin: 0;
}

.page-header h1 {
  font-size: clamp(2rem, 6vw, 3.5rem);
  line-height: 1.05;
}

.page-introduction {
  max-width: 42rem;
  margin: 0.75rem 0 0;
  color: #526071;
}

.transactions-panel {
  overflow: hidden;
  border: 1px solid #dbe2ea;
  border-radius: 1rem;
  background: #ffffff;
  box-shadow: 0 18px 50px rgb(15 23 42 / 8%);
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid #e8edf2;
}

.panel-heading h2 {
  font-size: 1.15rem;
}

.transaction-count {
  color: #64748b;
  font-size: 0.9rem;
}

.transaction-table-wrapper {
  overflow-x: auto;
}

.transaction-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.transaction-table th,
.transaction-table td {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #eef2f6;
  white-space: nowrap;
}

.transaction-table th {
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.transaction-table tbody tr:last-child td {
  border-bottom: 0;
}

.transaction-table tbody tr:hover {
  background: #f8fafc;
}

.transaction-type {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: capitalize;
}

.transaction-type--income {
  color: #166534;
  background: #dcfce7;
}

.transaction-type--spending {
  color: #9f1239;
  background: #ffe4e6;
}

.transaction-amount {
  color: #be123c;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  text-align: right;
}

.transaction-amount--income {
  color: #15803d;
}

.status-message {
  margin: 0;
  padding: 2rem 1.5rem;
  color: #526071;
}

.status-message--error {
  color: #991b1b;
  background: #fef2f2;
}

@media (max-width: 700px) {
  .app-shell {
    padding: 2rem 0;
  }

  .transaction-table th,
  .transaction-table td {
    padding: 0.85rem 1rem;
  }
}
```

The tutorial 1 global styles in `src/index.css` still provide the page's font,
background, text colour, and `box-sizing` rule. Component-specific styles stay
in `App.css` for now. A larger application might split styles alongside each
component, but the single file keeps this first feature easy to follow.

## Step 6: check the successful state

Open the URL printed by Vite, normally <http://localhost:5173>. If the database
already contains transactions, they should appear newest first.

You can also inspect the backend response directly:

```sh
curl http://127.0.0.1:5001/api/transactions
```

Check that:

- each API transaction produces one table row;
- income has a plus sign and green styling;
- spending has a minus sign and red styling;
- money is displayed as GBP;
- an absent description displays `No description`;
- the count matches `pagination.total_items`;
- dates and categories match the JSON response.

Then ask TypeScript and the linter to check the code:

```sh
cd ~/finance-app/frontend
npm run build
npm run lint
```

Fix any reported error before continuing. A successful production build proves
that all imported files exist and the component props agree with their types.

## Step 7: check loading, error, and empty states

A good data-driven interface is more than its successful state.

### Loading

In the browser developer tools, open the Network panel and select a slow network
throttling option. Refresh the page. You should briefly see:

```text
Loading transactions…
```

Return the network setting to its normal value afterwards.

### Error

Stop the Flask development server while leaving Vite running, then refresh the
page. The panel should show an error instead of remaining on the loading message
or displaying an empty table.

Restart Flask before the next check.

### Empty

Do not delete useful database records merely to test this state. One simple
temporary check is to change the request path in `App.tsx` to a valid filter
that matches no records, for example:

```ts
const response = await apiRequest<TransactionsResponse>(
  "/transactions?search=a-description-that-does-not-exist",
);
```

Refresh and check that `No transactions yet.` appears. Then restore the path to
`/transactions`.

Run the checks again after restoring it:

```sh
npm run build
npm run lint
```

## Exercise: use singular and plural count labels

The header currently displays `1 total` and `2 total`. Change it to display:

```text
1 transaction
2 transactions
```

Try this yourself before reading the reference solution. You need a conditional
expression and `pagination.total_items`.

### Reference solution

Replace the count `<span>` in `App.tsx` with:

```tsx
<span className="transaction-count">
  {pagination.total_items}{" "}
  {pagination.total_items === 1 ? "transaction" : "transactions"}
</span>
```

`{" "}` inserts one visible space between two JSX expressions. The ternary
chooses the singular noun only for exactly one item.

This is **derived data**: it can be calculated from `pagination`, so it does not
need another `useState`. Keeping derived values out of state avoids storing two
values that could disagree.

## Common problems

### The browser reports a network error

Confirm that Flask is running on port 5001 and that `frontend/.env` contains the
correct base URL. Restart Vite after changing an environment file because Vite
reads it when the development server starts.

### The API reports a CORS error

Complete the CORS setup from Tutorial 1 and restart Flask. The frontend and
backend run on different origins during development, so the API must explicitly
allow the Vite origin.

### `response.data` or `response.pagination` is undefined

Use the browser Network panel or `curl` to inspect the response. The current
backend returns an object containing both members. Do not type the response as
`Transaction[]`; the array is nested inside `data`.

### The page makes two requests in development

React Strict Mode checks effects by running an extra development-only setup and
cleanup cycle. A read-only GET request is safe to repeat, and the cleanup in
this tutorial ignores the obsolete result. The production build does not
perform this check.

### A date is displayed one day early

Confirm that `formatDate` constructs the date from separate year, month, and day
numbers. Avoid `new Date(transaction.transaction_date)` for a date-only API
value.

### TypeScript says a value may be null

Do not silence the warning with a type assertion. Handle the missing value, as
the row does with `transaction.description ?? "No description"`, or narrow it
with a condition before using it.

## What you learned

You now have a read-only transaction history backed by the Flask API. You used:

- TypeScript interfaces to model the complete API response;
- `useState` to store data and request status;
- `useEffect` to synchronize a component with the API;
- props to pass server data into presentation components;
- `map` and stable keys to render an array;
- conditional rendering for loading, error, empty, and success states;
- `Intl` formatters to present money and dates;
- semantic table markup and live status roles for accessibility.

The next tutorial will load categories and add a controlled form for creating a
transaction. After a successful request, the new record will appear in this
list.

## Commit the milestone

Review the files changed in this tutorial:

```sh
cd ~/finance-app
git status
git diff -- frontend/src
```

Then commit the working transaction history:

```sh
git add frontend/src/App.tsx \
  frontend/src/App.css \
  frontend/src/types.ts \
  frontend/src/components/TransactionList.tsx \
  frontend/src/components/TransactionRow.tsx
git commit -m "Display transaction history in React"
```
