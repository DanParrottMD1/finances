# Tutorial 3: create transactions with a React form

Tutorial 2 displayed transactions from the API. In this tutorial you will add a
form that loads the available categories and creates a transaction with:

```text
GET  /api/categories
POST /api/transactions
```

Along the way you will learn how React controls form fields, how a child
component reports an event to its parent, and why form values do not always have
the same TypeScript types as saved data.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Load and display categories | 10 minutes |
| Build the controlled form | 20 minutes |
| Submit a transaction | 15 minutes |
| Connect the form to the list | 10 minutes |
| Check errors and review | 5 minutes |

## What we are building

The page will contain an **Add a transaction** form above the transaction list.
The form collects:

- a positive amount;
- a transaction date;
- an optional description; and
- one of the categories stored by the backend.

Submitting it sends JSON in the API's existing format:

```json
{
  "amount": "42.75",
  "transaction_date": "2026-08-25",
  "description": "Weekly shop",
  "category_id": 2
}
```

The backend responds with the complete saved transaction, including its new ID
and nested category. Only then will the frontend add it to the list. This is not
an optimistic update: the interface does not pretend that a save succeeded
before the server confirms it.

## Before you start

Complete Tutorials 1 and 2. Start MariaDB, Flask on port 5001, and the Vite
development server as described in those tutorials. Make sure the transaction
list loads in the browser.

The form needs at least one category. Check the existing categories with:

```sh
curl http://127.0.0.1:5001/api/categories
```

If `data` is empty, use the backend tutorial to create a category before testing
a successful submission. This tutorial will handle the empty state in the UI,
but category creation belongs to a later tutorial.

Create a branch for this work:

```sh
cd ~/finance-app
git switch -c add-transaction-form
```

## Step 1: add a type for the category response

Tutorial 2 added the domain and response types in `frontend/src/types.ts`. The
categories endpoint returns an object whose `data` property is an array. Add
this type alongside the existing response types:

```ts
export interface CategoriesResponse {
  data: Category[]
}

export interface TransactionResponse {
  data: Transaction
}
```

`CategoriesResponse` matches the categories JSON:

```json
{
  "data": [
    {
      "id": 2,
      "description": "Groceries",
      "category_type": "spending"
    }
  ]
}
```

`Category` and `Transaction` are domain types: each describes one saved record.
The two new interfaces are transport types: they describe the JSON wrappers
sent over HTTP. The POST endpoint returns one transaction, so its `data` is a
`Transaction`; the GET endpoint returns several categories, so its `data` is a
`Category[]`.

## Step 2: create the form component

Create `frontend/src/components/TransactionForm.tsx`:

```tsx
import { useState, type FormEvent } from 'react'

import { apiRequest } from '../api'
import type { Category, TransactionResponse } from '../types'

interface TransactionFormProps {
  categories: Category[]
  onCreated: () => void | Promise<void>
}

export function TransactionForm({
  categories,
  onCreated,
}: TransactionFormProps) {
  const [amount, setAmount] = useState('')
  const [transactionDate, setTransactionDate] = useState('')
  const [description, setDescription] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    setError(null)

    try {
      await apiRequest<TransactionResponse>('/transactions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          amount,
          transaction_date: transactionDate,
          description: description.trim() || null,
          category_id: Number(categoryId),
        }),
      })

      await onCreated()
      setAmount('')
      setTransactionDate('')
      setDescription('')
      setCategoryId('')
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : 'Could not create the transaction.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  if (categories.length === 0) {
    return (
      <section aria-labelledby="transaction-form-heading">
        <h2 id="transaction-form-heading">Add a transaction</h2>
        <p>You need to create a category before adding a transaction.</p>
      </section>
    )
  }

  return (
    <section aria-labelledby="transaction-form-heading">
      <h2 id="transaction-form-heading">Add a transaction</h2>

      <form onSubmit={handleSubmit}>
        <label htmlFor="amount">Amount</label>
        <input
          id="amount"
          name="amount"
          type="number"
          min="0.01"
          max="99999999.99"
          step="0.01"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          required
        />

        <label htmlFor="transaction-date">Date</label>
        <input
          id="transaction-date"
          name="transaction_date"
          type="date"
          value={transactionDate}
          onChange={(event) => setTransactionDate(event.target.value)}
          required
        />

        <label htmlFor="description">Description</label>
        <input
          id="description"
          name="description"
          type="text"
          maxLength={255}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />

        <label htmlFor="category">Category</label>
        <select
          id="category"
          name="category_id"
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
          required
        >
          <option value="">Choose a category</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.description} ({category.category_type})
            </option>
          ))}
        </select>

        {error !== null && <p role="alert">{error}</p>}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : 'Add transaction'}
        </button>
      </form>
    </section>
  )
}
```

Do not worry about elaborate styling yet. The labels and standard HTML controls
give us a usable form that we can improve later.

### Controlled inputs

Each field is a **controlled input**. React state is the source of truth:

```tsx
const [amount, setAmount] = useState('')

<input
  value={amount}
  onChange={(event) => setAmount(event.target.value)}
/>
```

When the user types, the browser fires a change event. The handler saves the
new value in state, React renders again, and `value` puts that state into the
input. This provides one predictable place to read or reset every field.

Even a `type="number"` input reports its value as a string. An empty input is
also naturally represented by `''`, so keeping editable values as strings is
more convenient than forcing incomplete input into domain types.

The conversion happens at the API boundary:

```ts
category_id: Number(categoryId)
```

The backend accepts the decimal amount as a string, which preserves the exact
text entered for money. It returns saved amounts as strings for the same reason.

### The typed submit event

`FormEvent<HTMLFormElement>` tells TypeScript that `event` came from a form:

```ts
async function handleSubmit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault()
}
```

Browsers normally submit a form by navigating to a new page. `preventDefault()`
stops that navigation so React can send the request and update the current page.

The inline change handlers do not need explicit event types. TypeScript infers
them from the `<input>` or `<select>` that owns the handler. Explicit types are
most useful where inference no longer has enough context, as with the named
`handleSubmit` function.

### Submission state and backend errors

`isSubmitting` disables the button while the request is in progress. This makes
the current state visible and prevents an accidental double submission.

The `try` block handles success, `catch` displays an error, and `finally` runs in
both cases. Tutorial 1's `apiRequest` reads the backend's `{ "error": "..." }`
response and throws an `ApiError` with that message. Consequently, validation
such as an amount with too many decimal places appears in the form without
duplicating every backend business rule in React.

HTML attributes such as `required`, `min`, and `maxLength` still provide quick
feedback for obvious mistakes. The backend remains the authority because a
client can bypass browser validation and because rules must be enforced for
every API consumer.

Notice that the form fields reset only after `apiRequest` succeeds. When a
request fails, the values remain in place so the user can correct and resubmit
them.

## Step 3: load categories in App

Open `frontend/src/App.tsx`. Add the imports for the form and category type:

```tsx
import { TransactionForm } from './components/TransactionForm'
import type { CategoriesResponse, Category, Transaction } from './types'
```

Inside `App`, add state for categories:

```tsx
const [categories, setCategories] = useState<Category[]>([])
const [categoriesError, setCategoriesError] = useState<string | null>(null)
const [areCategoriesLoading, setAreCategoriesLoading] = useState(true)
```

Add this effect alongside the transaction-loading effect from Tutorial 2:

```tsx
useEffect(() => {
  async function loadCategories() {
    try {
      const response = await apiRequest<CategoriesResponse>('/categories')
      setCategories(response.data)
    } catch (caughtError) {
      setCategoriesError(
        caughtError instanceof Error
          ? caughtError.message
          : 'Could not load categories.',
      )
    } finally {
      setAreCategoriesLoading(false)
    }
  }

  void loadCategories()
}, [])
```

The empty dependency array means this effect starts once when `App` is mounted.
Categories are reference data for the form, so there is no reason to request
them after every field change or transaction creation.

## Step 4: refresh the list after a successful save

The backend sorts transactions by date and ID and returns only the first 20.
Adding the returned transaction to the start of the existing array would be
wrong when somebody enters an older date, and could temporarily display 21
rows. Refetch the authoritative first page instead.

In the React import at the top of `App.tsx`, add `useCallback`:

```tsx
import { useCallback, useEffect, useState } from 'react'
```

Replace the transaction-loading effect from Tutorial 2 with this callback and
effect. Keep the existing transaction state variables unchanged:

```tsx
const loadTransactions = useCallback(async () => {
  setIsLoading(true)
  setErrorMessage(null)

  try {
    const response = await apiRequest<TransactionsResponse>('/transactions')
    setTransactions(response.data)
    setPagination(response.pagination)
  } catch (caughtError) {
    setErrorMessage(
      caughtError instanceof Error
        ? caughtError.message
        : 'Could not load transactions.',
    )
  } finally {
    setIsLoading(false)
  }
}, [])

useEffect(() => {
  void loadTransactions()
}, [loadTransactions])
```

`useCallback` preserves the function's identity between renders. This lets the
effect name it as a dependency without starting again after every state update.
The callback has no changing dependencies of its own, so its array is empty.

Still inside `App`, add this function:

```tsx
async function handleTransactionCreated() {
  await loadTransactions()
}
```

Then render the form before the transaction list. Keep the loading and error UI
from Tutorial 2 around `TransactionList` unchanged:

```tsx
{areCategoriesLoading && <p>Loading categories…</p>}

{categoriesError !== null && <p role="alert">{categoriesError}</p>}

{!areCategoriesLoading && categoriesError === null && (
  <TransactionForm
    categories={categories}
    onCreated={handleTransactionCreated}
  />
)}
```

The relevant component flow now looks like this:

```text
App owns transactions and categories
  ├── TransactionForm receives categories
  │     └── awaits onCreated() after the server accepts the POST
  └── TransactionList receives transactions
```

The form cannot directly change state owned by `App`. Instead, the parent passes
it a callback as a prop. After the server confirms the save, the form awaits
that callback. `App` then reloads the sorted, paginated server result before the
form clears its fields.

This pattern is called **lifting state up**: shared state lives in the nearest
parent that needs to coordinate its children. The form creates data, the list
displays data, and `App` connects them.

This is also the first example of sharing a callback through props. Its
`() => void | Promise<void>` type says it takes no arguments and may finish
immediately or later. This tutorial supplies an asynchronous callback, and the
form awaits it so the interface does not report the workflow as finished while
the transaction list is still refreshing.

### Form state and domain state have different jobs

There are now two useful kinds of state:

- `amount`, `transactionDate`, `description`, and `categoryId` are temporary
  form state. They can be empty or incomplete while somebody types.
- `transactions` contains complete `Transaction` objects accepted and returned
  by the server. Each object has an ID and nested category.

Do not create a fake `Transaction` from the form fields and add it immediately.
It would not yet have a real server ID, and the category details or normalized
values could differ from the saved record. Waiting for the POST to succeed and
then loading the server's first page keeps the domain state trustworthy.

## Step 5: check the completed feature

Open the Vite URL shown in the terminal, normally
`http://localhost:5173`. Check the following successful path:

1. The category select contains the categories returned by the backend.
2. Enter an amount, date, optional description, and category.
3. Select **Add transaction**.
4. The button changes to **Saving…** while the request is running.
5. The fields clear and the saved transaction appears at the top of the list.
6. Refresh the browser and confirm that the transaction is still present.

The refresh is important: it proves the backend persisted the transaction rather
than the item existing only in React state.

Now check an error returned by the backend. Browser validation blocks many
simple invalid values, so use the browser's developer tools to temporarily
remove the amount input's `step` attribute, enter `10.123`, and submit. The form
should retain its values and show the backend message:

```text
amount must have at most 2 decimal places.
```

Restore the `step` attribute by refreshing the page.

Finally, stop Flask and submit again. The form should show a connection error,
keep the entered values, and re-enable the button. Restart Flask afterwards.

Run the TypeScript and lint checks from Tutorial 1:

```sh
cd ~/finance-app/frontend
npm run build
npm run lint
```

Both commands should finish without errors.

## Common problems

### The category select is empty

Call `GET /api/categories` directly and inspect its `data` array. If the backend
has categories, check the browser network panel for the request URL and response.
Also confirm Flask is running on the port configured by `VITE_API_BASE_URL`.

### The backend says category_id must be a positive integer

Make sure the select is required and the request converts its string value:

```ts
category_id: Number(categoryId)
```

Without `Number`, selecting category 2 sends `"2"`, but the API requires the
JSON number `2`.

### The page reloads when the form is submitted

Check that the handler accepts the event and calls:

```ts
event.preventDefault()
```

Also attach the handler to `<form onSubmit={handleSubmit}>`, not only to the
button's click event. Form submission must also work when a user presses Enter.

### A failed request clears the fields

The four reset calls must be inside the `try` block after `apiRequest` and
`onCreated`. The `finally` block should only restore `isSubmitting`.

## Review exercises

1. Add `aria-live="polite"` to a small status element and announce when a
   transaction has been saved successfully.
2. Group the category options under `<optgroup>` elements labelled **Income**
   and **Spending**. Derive the two arrays from `categories`; do not add another
   API request.
3. Explain why `categoryId` is a string while the user edits the form but
   `Transaction.category_id` is a number.
4. Explain what could go wrong if the form added a transaction before the POST
   request completed.

## Commit the milestone

Review the changed files, then commit the completed feature:

```sh
cd ~/finance-app
git status
git add frontend/src/App.tsx frontend/src/components/TransactionForm.tsx \
  frontend/src/types.ts
git commit -m "Add transaction creation form"
```

You now have a complete create workflow: React loads reference data, controls
the user's input, sends a typed API request, displays backend errors, and shares
the saved transaction with the list through a callback. The next tutorial will
add automated tests for these behaviours.
