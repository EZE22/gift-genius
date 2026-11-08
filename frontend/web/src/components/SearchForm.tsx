import { forwardRef, useId } from "react";

export const MAX_DESCRIPTION = 1000;
export const MAX_BUDGET = 10_000;

export function parseBudget(text: string): number | null {
  const value = Number(text.trim().replace(/[$,]/g, ""));
  return text.trim() && Number.isFinite(value) && value >= 1 && value <= MAX_BUDGET ? value : null;
}

interface Props {
  description: string;
  budget: string;
  busy: boolean;
  onDescription: (value: string) => void;
  onBudget: (value: string) => void;
  onSubmit: () => void;
}

export const SearchForm = forwardRef<HTMLTextAreaElement, Props>(function SearchForm(
  { description, budget, busy, onDescription, onBudget, onSubmit },
  descriptionRef,
) {
  const id = useId();
  const budgetValue = parseBudget(budget);
  const budgetInvalid = budget.trim() !== "" && budgetValue === null;
  const ready = description.trim() !== "" && budgetValue !== null && !busy;

  return (
    <form
      className="search-form"
      aria-label="Gift search"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) onSubmit();
      }}
    >
      <div className="field">
        <label className="field-label" htmlFor={`${id}-description`}>
          Who is the gift for?
        </label>
        <p className="hint" id={`${id}-description-hint`}>
          Their interests, age, what they already have. A sentence or two is enough.
        </p>
        <textarea
          ref={descriptionRef}
          id={`${id}-description`}
          aria-describedby={`${id}-description-hint`}
          rows={4}
          maxLength={MAX_DESCRIPTION}
          value={description}
          disabled={busy}
          placeholder="My brother is 30, loves weekend camping trips and just got into trail running."
          onChange={(e) => onDescription(e.target.value)}
        />
      </div>
      <div className="field budget-field">
        <label className="field-label" htmlFor={`${id}-budget`}>
          Budget per gift
        </label>
        <div className="money-input">
          <span aria-hidden="true">$</span>
          <input
            id={`${id}-budget`}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={budget}
            disabled={busy}
            placeholder="50"
            aria-invalid={budgetInvalid}
            aria-describedby={budgetInvalid ? `${id}-budget-error` : undefined}
            onChange={(e) => onBudget(e.target.value)}
          />
          <span className="unit">dollars</span>
        </div>
        {budgetInvalid && (
          <p className="field-error" id={`${id}-budget-error`}>
            Enter a number from 1 to 10,000.
          </p>
        )}
      </div>
      <button type="submit" className="primary" disabled={!ready}>
        {busy ? "Finding gifts…" : "Find gifts"}
      </button>
    </form>
  );
});
