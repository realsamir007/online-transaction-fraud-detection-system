import type { ReactNode } from "react";

type Segment<T extends string> = {
  value: T;
  label: ReactNode;
};

type Props<T extends string> = {
  value: T;
  onChange: (value: T) => void;
  options: Segment<T>[];
};

export function SegmentedControl<T extends string>({ value, onChange, options }: Props<T>) {
  return (
    <div className="ui-segmented" role="tablist" aria-label="Authentication mode">
      {options.map((option) => {
        const isActive = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={isActive ? "active" : ""}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
