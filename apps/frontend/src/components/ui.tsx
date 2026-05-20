import { clsx, type ClassValue } from "clsx";
import type * as React from "react";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function Card({ className, children }: React.PropsWithChildren<{ className?: string }>) {
  return <div className={cn("rounded-card border border-pearl/80 bg-white/82 p-5 shadow-soft", className)}>{children}</div>;
}

export function Button({
  className,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const variants = {
    primary: "bg-rose text-white hover:bg-clay",
    secondary: "bg-pearl text-ink hover:bg-[#ead9cf]",
    ghost: "bg-transparent text-ink hover:bg-pearl",
    danger: "bg-[#c45e5b] text-white hover:bg-[#ad4c49]"
  };
  return (
    <button
      className={cn("inline-flex h-10 items-center justify-center gap-2 rounded-card px-4 text-sm font-semibold transition disabled:opacity-50", variants[variant], className)}
      {...props}
    />
  );
}

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("h-10 w-full rounded-card border border-pearl bg-white px-3 text-sm outline-none ring-rose/20 focus:ring-4", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("min-h-28 w-full rounded-card border border-pearl bg-white p-3 text-sm outline-none ring-rose/20 focus:ring-4", className)} {...props} />;
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn("h-10 w-full rounded-card border border-pearl bg-white px-3 text-sm outline-none ring-rose/20 focus:ring-4", className)} {...props} />;
}

export function Badge({ children, tone = "neutral" }: React.PropsWithChildren<{ tone?: "green" | "yellow" | "red" | "neutral" }>) {
  const tones = {
    green: "bg-sage/15 text-sage",
    yellow: "bg-[#f4d99e]/45 text-[#8c6224]",
    red: "bg-[#f4c7c4]/55 text-[#a6423f]",
    neutral: "bg-pearl text-clay"
  };
  return <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-semibold", tones[tone])}>{children}</span>;
}

export function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-2xl font-bold tracking-normal text-ink">{title}</h1>
      {subtitle ? <p className="mt-1 text-sm text-clay">{subtitle}</p> : null}
    </div>
  );
}
