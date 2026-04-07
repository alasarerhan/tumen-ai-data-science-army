import React, { useState } from "react";
import { CalendarClock, Clock } from "lucide-react";
import { Button } from "../ui/button";

interface NaturalScheduleInputProps {
  value: string;
  onChange: (value: string, cron: string) => void;
  cronValue: string;
  disabled?: boolean;
}

const EXAMPLES = [
  { label: "Her gün 09:00'da", value: "her gün 09:00'da" },
  { label: "Her pazartesi 10:30'da", value: "her pazartesi 10:30'da" },
  { label: "Her 4 saatte bir", value: "her 4 saatte bir" },
  { label: "Every day at 9am", value: "every day at 9am" },
  { label: "Every monday at 10:30", value: "every monday at 10:30" },
  { label: "Every 2 hours", value: "every 2 hours" },
];

export function NaturalScheduleInput({
  value,
  onChange,
  cronValue,
  disabled = false,
}: NaturalScheduleInputProps) {
  const [mode, setMode] = useState<"natural" | "cron">("natural");

  const handleExampleClick = (exampleValue: string) => {
    onChange(exampleValue, "");
  };

  const handleNaturalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value, "");
  };

  const handleCronChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange("", e.target.value);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Button
          variant={mode === "natural" ? "secondary" : "ghost"}
          size="xs"
          onClick={() => setMode("natural")}
          disabled={disabled}
        >
          <CalendarClock size={12} />
          Natural
        </Button>
        <Button
          variant={mode === "cron" ? "secondary" : "ghost"}
          size="xs"
          onClick={() => setMode("cron")}
          disabled={disabled}
        >
          <Clock size={12} />
          Cron
        </Button>
      </div>

      {mode === "natural" ? (
        <div className="space-y-2">
          <input
            value={value}
            onChange={handleNaturalChange}
            placeholder="e.g., her gün 09:00'da"
            className="h-8 w-full rounded-md border border-slate-300 px-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            disabled={disabled}
          />
          <div className="flex flex-wrap gap-1">
            {EXAMPLES.map((example) => (
              <button
                key={example.value}
                type="button"
                onClick={() => handleExampleClick(example.value)}
                className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={disabled}
              >
                {example.label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-1">
          <input
            value={cronValue}
            onChange={handleCronChange}
            placeholder="0 9 * * *"
            className="h-8 w-full rounded-md border border-slate-300 px-2 font-mono text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            disabled={disabled}
          />
          <p className="text-xs text-slate-400">
            Format: minute hour day-of-month month day-of-week
          </p>
        </div>
      )}
    </div>
  );
}
