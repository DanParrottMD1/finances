# Tutorial 6: edit and delete transactions

The frontend can list, create, filter, and paginate transactions. In this
tutorial you will complete transaction management with the backend endpoints
added in Backend Tutorial 4:

```text
PATCH  /api/transactions/<id>
DELETE /api/transactions/<id>
```

You will reuse the existing transaction form for editing, add an accessible
delete confirmation, and keep the filtered, paginated list synchronized with
the server after each change.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Refactor the form for create and edit modes | 20 minutes |
| Add row actions and selection state | 10 minutes |
| Add deletion and confirmation | 15 minutes |
| Extend the automated tests | 10 minutes |
| Check the complete workflow and commit | 5 minutes |

## What we are building

Each transaction row will gain **Edit** and **Delete** actions. Editing replaces
the creation form temporarily with a form populated from the selected
transaction. Saving sends all four editable fields to `PATCH`, then returns to
creation mode.

Deleting first opens a confirmation dialog. The application sends `DELETE`
only after confirmation, and closes the dialog only after the server responds
successfully.

Both mutations finish by requesting the applicable filtered page again:

```text
user action
    ↓
PATCH or DELETE
    ↓ server confirms success
GET /transactions?<applied filters>&page=<safe page>
    ↓
render authoritative results
```

This matters when an edit changes a transaction so it no longer matches the
current filters, or a deletion removes the final item from a page.

## Before you start

Complete Tutorial 5 and make sure all frontend tests pass:

```sh
cd ~/finance-app/frontend
npm test
```

Create a branch:

```sh
cd ~/finance-app
git switch -c edit-delete-transactions
```

No new npm packages are needed. This tutorial continues to use Vitest, React
Testing Library, user-event, and MSW from Tutorial 4.

## Step 1: make `TransactionForm` reusable

The creation form already owns temporary strings for the editable fields. An
editing form needs the same controls, validation, submission state, and error
display. Copying the component would make the two versions drift apart, so we
will give one component two modes.

Replace `frontend/src/components/TransactionForm.tsx` with:

```tsx
import { useState, type FormEvent } from "react";

import { apiRequest } from "../api";
import type { Category, Transaction, TransactionResponse } from "../types";

interface TransactionFormProps {
  categories: Category[];
  transaction?: Transaction;
  onSaved: (transaction: Transaction) => void;
  onCancel?: () => void;
}

export function TransactionForm({
  categories,
  transaction,
  onSaved,
  onCancel,
}: TransactionFormProps) {
  const isEditing = transaction !== undefined;
  const [amount, setAmount] = useState(transaction?.amount ?? "");
  const [transactionDate, setTransactionDate] = useState(
    transaction?.transaction_date ?? "",
  );
  const [description, setDescription] = useState(
    transaction?.description ?? "",
  );
  const [categoryId, setCategoryId] = useState(
    transaction?.category_id.toString() ?? "",
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const path = isEditing
      ? `/transactions/${transaction.id}`
      : "/transactions";
    const method = isEditing ? "PATCH" : "POST";

    try {
      const response = await apiRequest<TransactionResponse>(path, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          amount,
          transaction_date: transactionDate,
          description: description.trim() || null,
          category_id: Number(categoryId),
        }),
      });

      onSaved(response.data);

      if (!isEditing) {
        setAmount("");
        setTransactionDate("");
        setDescription("");
        setCategoryId("");
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : `Could not ${isEditing ? "update" : "create"} the transaction.`,
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (categories.length === 0) {
    return (
      <section aria-labelledby="transaction-form-heading">
        <h2 id="transaction-form-heading">
          {isEditing ? "Edit transaction" : "Add a transaction"}
        </h2>
        <p>Transactions need at least one available category.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="transaction-form-heading">
      <h2 id="transaction-form-heading">
        {isEditing ? "Edit transaction" : "Add a transaction"}
      </h2>

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
          {isSubmitting
            ? "Saving…"
            : isEditing
              ? "Save changes"
              : "Add transaction"}
        </button>

        {isEditing && (
          <button type="button" onClick={onCancel} disabled={isSubmitting}>
            Cancel editing
          </button>
        )}
      </form>
    </section>
  );
}
```

### One component, two modes

The optional `transaction` prop decides the mode:

| Prop | Mode | Initial values | Request |
| --- | --- | --- | --- |
| omitted | create | empty strings | `POST /transactions` |
| supplied | edit | saved transaction | `PATCH /transactions/<id>` |

The backend supports partial updates, but sending all four editable fields is
appropriate here because the form displays and validates the complete editable
record. `id` and the nested `category` are not editable and are not sent.

The existing `onCreated` callback has become `onSaved`, because both a created
transaction and an updated transaction come back in the same
`TransactionResponse` shape.

The cancel button has `type="button"`. A button inside a form defaults to submit;
without this type, cancelling could accidentally send a PATCH request.

### Form state is initialized, not continuously copied

The arguments to `useState` are read when this component instance first mounts:

```tsx
const [amount, setAmount] = useState(transaction?.amount ?? "");
```

They are not read again whenever `transaction` changes. In Step 4, `App` will
give the editing form a `key` based on the transaction ID. Selecting a different
ID then creates a fresh form instance with the correct starting values. This is
a useful application of identity: the database ID tells React that these are
different editing tasks.

## Step 2: add row actions

Update `TransactionRowProps` in
`frontend/src/components/TransactionRow.tsx`:

```tsx
interface TransactionRowProps {
  transaction: Transaction;
  onEdit: (transaction: Transaction) => void;
  onDeleteRequest: (transaction: Transaction) => void;
}
```

Update the function parameters and add a useful name for its action buttons:

```tsx
export function TransactionRow({
  transaction,
  onEdit,
  onDeleteRequest,
}: TransactionRowProps) {
  const isIncome = transaction.category.category_type === "income";
  const transactionName =
    transaction.description ?? transaction.category.description;
```

At the end of the row, after the amount `<td>`, add:

```tsx
<td>
  <button
    type="button"
    aria-label={`Edit ${transactionName}`}
    onClick={() => onEdit(transaction)}
  >
    Edit
  </button>
  <button
    type="button"
    aria-label={`Delete ${transactionName}`}
    onClick={() => onDeleteRequest(transaction)}
  >
    Delete
  </button>
</td>
```

The visible button text stays compact in the table, while the accessible name
identifies the row. A screen reader announces “Edit Weekly shop” rather than
several indistinguishable “Edit” buttons.

Now update `frontend/src/components/TransactionList.tsx`. Extend its props:

```tsx
interface TransactionListProps {
  transactions: Transaction[];
  onEdit: (transaction: Transaction) => void;
  onDeleteRequest: (transaction: Transaction) => void;
}
```

Accept the new props:

```tsx
export function TransactionList({
  transactions,
  onEdit,
  onDeleteRequest,
}: TransactionListProps) {
```

Add one header after **Amount**:

```tsx
<th scope="col">Actions</th>
```

Finally, pass the callbacks to each row:

```tsx
{transactions.map((transaction) => (
  <TransactionRow
    key={transaction.id}
    transaction={transaction}
    onEdit={onEdit}
    onDeleteRequest={onDeleteRequest}
  />
))}
```

Events now travel up through two component levels. The row knows which button
was selected, but `App` owns the transaction collection and performs network
requests, so `App` decides what the action means.

## Step 3: extract a refresh function in `App`

Tutorial 5 used `refreshKey` to rerun the current transaction request. In
`frontend/src/App.tsx`, add a small named function inside `App`:

```tsx
function refreshTransactions() {
  setRefreshKey((currentKey) => currentKey + 1);
}
```

Replace the direct `setRefreshKey` call in the creation success handler:

```tsx
function handleTransactionCreated() {
  setPage(1);
  refreshTransactions();
}
```

This is still the same Tutorial 5 behaviour: creation returns to page 1 and
refetches using `appliedFilters`. Naming it prepares us to reuse the operation
after editing and deleting.

## Step 4: add editing state to `App`

Add this state with the other `useState` calls:

```tsx
const [editingTransaction, setEditingTransaction] =
  useState<Transaction | null>(null);
```

The selected transaction is either a complete domain object or `null`. Storing
the object populates the form without another GET endpoint; its stable `id`
identifies the record for PATCH.

Add these handlers:

```tsx
function handleEdit(transaction: Transaction) {
  setEditingTransaction(transaction);
}

function handleTransactionSaved() {
  setEditingTransaction(null);
  setPage(1);
  refreshTransactions();
}
```

Replace the existing creation form rendering with this conditional block:

```tsx
{!areCategoriesLoading && categoriesError === null && (
  editingTransaction === null ? (
    <TransactionForm
      categories={categories}
      onSaved={handleTransactionSaved}
    />
  ) : (
    <TransactionForm
      key={editingTransaction.id}
      categories={categories}
      transaction={editingTransaction}
      onSaved={handleTransactionSaved}
      onCancel={() => setEditingTransaction(null)}
    />
  )
)}
```

Use `handleTransactionSaved` for creation too, and remove the old
`handleTransactionCreated`. Both operations should return to page 1 and load
the server's current results.

Pass the edit callback to the transaction list. We will add the delete callback
in the next step:

```tsx
<TransactionList
  transactions={transactions}
  onEdit={handleEdit}
  onDeleteRequest={handleDeleteRequest}
/>
```

`handleDeleteRequest` will exist after Step 5, so TypeScript may report it as
missing until that step is complete.

### Why refetch instead of changing the array locally?

After the PATCH response, this immutable update would correctly replace one
object without mutating React state:

```tsx
setTransactions((currentTransactions) =>
  currentTransactions.map((currentTransaction) =>
    currentTransaction.id === updatedTransaction.id
      ? updatedTransaction
      : currentTransaction,
  ),
);
```

But it cannot determine the complete filtered page. Changing a category or
date may cause the transaction to leave the current results, enter a different
sort position, or change the number of pages. The existing GET endpoint already
knows those rules. Refetching after server confirmation synchronizes all of
`transactions` and `pagination` together.

This differs from an optimistic update. We do not change visible domain data
while PATCH is pending. If PATCH fails, the form remains open with the user's
values and displays the backend error.

## Step 5: add an accessible delete confirmation

Add `useRef` to the React import in `App.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
```

Add four pieces of state and a button reference inside `App`:

```tsx
const [transactionToDelete, setTransactionToDelete] =
  useState<Transaction | null>(null);
const [isDeleting, setIsDeleting] = useState(false);
const [deleteError, setDeleteError] = useState<string | null>(null);
const deleteCancelButtonRef = useRef<HTMLButtonElement>(null);
```

When the confirmation appears, move keyboard focus into it:

```tsx
useEffect(() => {
  if (transactionToDelete !== null) {
    deleteCancelButtonRef.current?.focus();
  }
}, [transactionToDelete]);
```

Add the request, cancel, and confirmation handlers:

```tsx
function handleDeleteRequest(transaction: Transaction) {
  setEditingTransaction(null);
  setDeleteError(null);
  setTransactionToDelete(transaction);
}

function handleDeleteCancel() {
  setTransactionToDelete(null);
  setDeleteError(null);
}

async function handleDeleteConfirm() {
  if (transactionToDelete === null) {
    return;
  }

  setIsDeleting(true);
  setDeleteError(null);

  try {
    await apiRequest<void>(`/transactions/${transactionToDelete.id}`, {
      method: "DELETE",
    });

    const deletedLastItemOnPage = transactions.length === 1;
    setTransactionToDelete(null);

    if (deletedLastItemOnPage && page > 1) {
      setPage((currentPage) => currentPage - 1);
    } else {
      refreshTransactions();
    }
  } catch (caughtError) {
    setDeleteError(
      caughtError instanceof Error
        ? caughtError.message
        : "Could not delete the transaction.",
    );
  } finally {
    setIsDeleting(false);
  }
}
```

Tutorial 1's `apiRequest<void>` handles the backend's successful `204 No
Content` response without trying to parse JSON.

Render this confirmation near the end of `App`'s JSX, after the transaction
list and pagination controls:

```tsx
{transactionToDelete !== null && (
  <div
    className="confirmation-dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="delete-dialog-heading"
    aria-describedby="delete-dialog-description"
  >
    <h2 id="delete-dialog-heading">Delete transaction?</h2>
    <p id="delete-dialog-description">
      This will permanently delete {transactionToDelete.description ??
        transactionToDelete.category.description}.
    </p>

    {deleteError !== null && <p role="alert">{deleteError}</p>}

    <button
      ref={deleteCancelButtonRef}
      type="button"
      onClick={handleDeleteCancel}
      disabled={isDeleting}
    >
      Cancel
    </button>
    <button
      type="button"
      onClick={() => void handleDeleteConfirm()}
      disabled={isDeleting}
    >
      {isDeleting ? "Deleting…" : "Delete transaction"}
    </button>
  </div>
)}
```

This is a confirmation region, not a browser `window.confirm` call. Its dialog
role, accessible name, description, initial focus, and real buttons make its
purpose available to keyboard and assistive-technology users. A production
modal would additionally trap focus inside the dialog and restore focus to the
trigger when it closes; that is a useful extension exercise below.

The dialog remains open when DELETE fails, preserving context and displaying
the backend's message. Both buttons are disabled during the request, preventing
duplicate deletion or a state change while the request is unresolved.

### Why the last item on a page is special

Suppose page 3 contains one item. After deleting it, requesting page 3 would
produce an empty page even though page 2 still has transactions. The handler
therefore moves back one page. Changing `page` changes Tutorial 5's
`queryString`, so the transaction effect runs without also changing
`refreshKey`.

For every other deletion, the page remains valid and `refreshTransactions()`
reruns its current request. On page 1, deleting the last result correctly
refreshes page 1 and displays the filtered empty state.

The calculation uses `transactions.length`, the items on the displayed page,
not `pagination.total_items`, the count across every page.

## Step 6: extend the MSW tests

The test suite should prove the HTTP contract and user-visible result. Open
`frontend/src/App.test.tsx` and add `waitFor` to the Testing Library import if it
is not already present:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
```

The following test edits the default fixture. Add it inside the existing
`describe("App", ...)` block:

```tsx
it("edits a transaction and displays the saved result", async () => {
  const user = userEvent.setup();
  let savedTransaction = weeklyShop;

  server.use(
    http.get("*/api/transactions", () => {
      return HttpResponse.json({
        data: [savedTransaction],
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
    http.patch("*/api/transactions/10", async ({ request }) => {
      expect(await request.json()).toEqual({
        amount: "42.75",
        transaction_date: "2026-08-20",
        description: "Groceries and toiletries",
        category_id: 2,
      });

      savedTransaction = {
        ...weeklyShop,
        description: "Groceries and toiletries",
      };
      return HttpResponse.json({ data: savedTransaction });
    }),
  );

  render(<App />);
  await screen.findByText("Weekly shop");

  await user.click(screen.getByRole("button", { name: "Edit Weekly shop" }));

  expect(await screen.findByRole("heading", { name: "Edit transaction" }))
    .toBeInTheDocument();
  expect(screen.getByLabelText("Amount")).toHaveValue(42.75);
  expect(screen.getByLabelText("Date")).toHaveValue("2026-08-20");
  expect(screen.getByLabelText("Category")).toHaveValue("2");

  const description = screen.getByLabelText("Description");
  await user.clear(description);
  await user.type(description, "Groceries and toiletries");
  await user.click(screen.getByRole("button", { name: "Save changes" }));

  expect(await screen.findByText("Groceries and toiletries"))
    .toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Edit transaction" }))
    .not.toBeInTheDocument();
});
```

Add `weeklyShop` to the fixture import used by the test file:

```tsx
import { groceriesCategory, weeklyShop } from "./test/fixtures";
```

The handler changes `savedTransaction` before returning. The follow-up GET
therefore returns the same state that a real database would return after PATCH.
Without this stateful mock, the application's deliberate refetch would restore
the old fixture and the test would not model the server accurately.

Add a deletion test:

```tsx
it("confirms and deletes a transaction", async () => {
  const user = userEvent.setup();
  let transactions = [weeklyShop];

  server.use(
    http.get("*/api/transactions", () => {
      return HttpResponse.json({
        data: transactions,
        pagination: {
          page: 1,
          per_page: 10,
          total_items: transactions.length,
          total_pages: transactions.length === 0 ? 0 : 1,
          has_next: false,
          has_previous: false,
        },
      });
    }),
    http.delete("*/api/transactions/10", () => {
      transactions = [];
      return new HttpResponse(null, { status: 204 });
    }),
  );

  render(<App />);
  await screen.findByText("Weekly shop");

  await user.click(
    screen.getByRole("button", { name: "Delete Weekly shop" }),
  );

  const dialog = screen.getByRole("dialog", {
    name: "Delete transaction?",
  });
  expect(dialog).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();

  await user.click(screen.getByRole("button", { name: "Delete transaction" }));

  expect(await screen.findByText("No transactions yet.")).toBeInTheDocument();
  expect(screen.queryByText("Weekly shop")).not.toBeInTheDocument();
  await waitFor(() => {
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
```

The focus assertion protects part of the confirmation's accessibility, while
the final assertions prove that the UI waits for success, closes the dialog,
and refetches the list.

### Exercise: test deletion from the final page

Write one more test for the pagination edge case:

1. Make the GET handler inspect `new URL(request.url).searchParams`.
2. On page 1, return one transaction with `has_next: true` and
   `total_pages: 2`.
3. On page 2, return a different transaction as that page's only item.
4. Click **Next**, delete the page-2 transaction, and record its DELETE.
5. Assert that the next GET asks for `page=1` and that the page-1 transaction
   is visible again.

A reference handler for the important part is:

```tsx
const requestedPages: string[] = [];
let pageTwoExists = true;

http.get("*/api/transactions", ({ request }) => {
  const requestedPage = new URL(request.url).searchParams.get("page") ?? "1";
  requestedPages.push(requestedPage);

  if (requestedPage === "2" && pageTwoExists) {
    return HttpResponse.json({
      data: [pageTwoTransaction],
      pagination: {
        page: 2,
        per_page: 10,
        total_items: 2,
        total_pages: 2,
        has_next: false,
        has_previous: true,
      },
    });
  }

  return HttpResponse.json({
    data: [weeklyShop],
    pagination: {
      page: 1,
      per_page: 10,
      total_items: pageTwoExists ? 2 : 1,
      total_pages: 1,
      has_next: false,
      has_previous: false,
    },
  });
});
```

Create `pageTwoTransaction` by spreading `weeklyShop` and replacing at least
`id` and `description`. The DELETE handler should set `pageTwoExists = false`
and return 204. After confirmation, use `waitFor` to assert:

```tsx
expect(requestedPages[requestedPages.length - 1]).toBe("1");
expect(screen.getByText("Weekly shop")).toBeInTheDocument();
```

This test is valuable because a normal one-page deletion test cannot detect an
implementation that leaves the user stranded on an empty page.

## Step 7: manually check errors and filters

Start Flask and Vite, then use the browser to check these paths:

1. Apply a category or text filter and edit one of its results.
2. Confirm the edit form contains the saved amount, date, description, and
   category.
3. Select **Cancel editing**. Confirm no PATCH request appears in the browser's
   network panel.
4. Edit again, save a change that no longer matches the active filter, and
   confirm the transaction leaves the refetched results.
5. Select **Delete** on a transaction. Confirm keyboard focus moves to
   **Cancel**, then cancel and check that no DELETE request was sent.
6. Confirm deletion and check that the dialog closes only after the request
   succeeds.
7. Navigate to a final page containing one result, delete it, and confirm the
   application returns to the previous page.

To inspect failure behaviour, stop Flask after opening an edit form. Saving
should preserve the entered values and display an alert. Restart Flask, open a
delete confirmation, stop Flask again, and confirm deletion. The dialog should
remain open, show the error, and re-enable both buttons.

Run every project check:

```sh
cd ~/finance-app/frontend
npm test
npm run lint
npm run build
```

## Common problems

### Editing shows empty fields

Pass `transaction={editingTransaction}` and
`key={editingTransaction.id}` to the editing form. Also convert the numeric
category ID to a string when initializing the select:

```tsx
transaction?.category_id.toString() ?? ""
```

HTML select values are strings.

### The old description returns after saving

Make sure PATCH finishes before `onSaved` runs. In tests, make the GET mock
return the updated value after PATCH; in development, inspect the PATCH response
and following GET in the network panel.

### Deletion fails with a JSON parsing error

Call `apiRequest<void>`. A successful DELETE is `204 No Content`, and the API
helper from Tutorial 1 explicitly returns without parsing a body for status
204.

### The dialog closes when DELETE fails

Move `setTransactionToDelete(null)` into the successful path after
`await apiRequest`. The catch block should set `deleteError` without clearing
the selected transaction.

### Deleting the only item shows an empty later page

Check the displayed page length before clearing or refetching it:

```tsx
const deletedLastItemOnPage = transactions.length === 1;
```

If that is true and `page > 1`, decrement `page`; do not merely increment
`refreshKey`.

## Review exercises

1. After cancelling or successfully deleting, restore focus to the row button
   that opened the dialog. Store the trigger element or identify the row by ID.
2. Move the confirmation into a reusable `ConfirmationDialog` component. Which
   values and callbacks should its props contain?
3. Disable the row actions for a transaction while its mutation is pending,
   while keeping actions on other rows available.
4. Compare the server-confirmed refetch with an optimistic array update. What
   extra rollback state would an optimistic edit or deletion require?
5. Add a test in which PATCH returns `{ "error": "The selected category does
   not exist." }` with status 404. Confirm the edit form remains populated and
   its alert displays the backend message.

## Commit the milestone

Inspect and commit the application and test changes:

```sh
cd ~/finance-app
git status --short
git diff
git add frontend/src/App.tsx frontend/src/App.test.tsx \
  frontend/src/components/TransactionForm.tsx \
  frontend/src/components/TransactionList.tsx \
  frontend/src/components/TransactionRow.tsx \
  docs/frontend/06-edit-delete-transactions-tutorial.md
git commit -m "Add transaction editing and deletion"
```

The frontend now supports the complete transaction lifecycle. Selection state
identifies the record being changed, one form handles create and edit modes,
and filtered pagination is refreshed only after the server confirms each
mutation. The next tutorial will add navigation and category management.
