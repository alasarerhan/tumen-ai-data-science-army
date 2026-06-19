import React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

/** Public CVA variant API — exported for downstream button composition via `cva(b)` pattern. */
export const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap font-medium transition-colors duration-75 focus-visible:outline-none select-none disabled:cursor-not-allowed disabled:opacity-40 active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800 focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2",
        primary:
          "bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800 focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2",
        secondary:
          "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:shadow-sm active:bg-slate-100 focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2",
        outline:
          "border border-slate-300 bg-transparent text-slate-700 hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2",
        ghost:
          "bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2",
        destructive:
          "bg-red-600 text-white hover:bg-red-700 active:bg-red-800 focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2",
        link: "h-auto p-0 text-indigo-600 hover:underline focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2",
      },
      size: {
        xs: "h-7 rounded-[6px] px-2.5 text-xs gap-1",
        sm: "h-8 rounded-[6px] px-3 text-[13px] gap-1.5",
        default: "h-9 rounded-[6px] px-4 text-sm gap-1.5",
        md: "h-9 rounded-[6px] px-4 text-sm gap-1.5",
        lg: "h-10 rounded-[8px] px-4 text-sm gap-2",
        xl: "h-11 rounded-[8px] px-5 text-sm gap-2",
        icon: "h-9 w-9 rounded-[8px]",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
  leadingIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
  fullWidth?: boolean;
}

export function Button({
  variant,
  size,
  loading,
  leadingIcon,
  trailingIcon,
  fullWidth,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), fullWidth && "w-full", className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="size-4 animate-spin" />
      ) : leadingIcon ? (
        <span className="flex size-4 items-center justify-center">{leadingIcon}</span>
      ) : null}
      {children}
      {!loading && trailingIcon ? (
        <span className="flex size-4 items-center justify-center">{trailingIcon}</span>
      ) : null}
    </button>
  );
}
