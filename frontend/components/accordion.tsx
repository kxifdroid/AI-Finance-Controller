"use client";

import { createContext, useContext, useId, useState, ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface AccordionContextValue {
  openValue: string | null;
  setOpenValue: (value: string | null) => void;
}

const AccordionContext = createContext<AccordionContextValue | null>(null);

interface AccordionItemContextValue {
  value: string;
  isOpen: boolean;
  toggle: () => void;
}

const AccordionItemContext = createContext<AccordionItemContextValue | null>(null);

export function Accordion({
  children,
  className,
  defaultValue,
}: {
  type?: "single";
  collapsible?: boolean;
  children: ReactNode;
  className?: string;
  defaultValue?: string;
}) {
  const [openValue, setOpenValue] = useState<string | null>(defaultValue ?? null);
  return (
    <AccordionContext.Provider value={{ openValue, setOpenValue }}>
      <div className={className}>{children}</div>
    </AccordionContext.Provider>
  );
}

export function AccordionItem({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const ctx = useContext(AccordionContext);
  if (!ctx) throw new Error("AccordionItem must be used within an Accordion");
  const isOpen = ctx.openValue === value;
  const toggle = () => ctx.setOpenValue(isOpen ? null : value);

  return (
    <AccordionItemContext.Provider value={{ value, isOpen, toggle }}>
      <div className={className}>{children}</div>
    </AccordionItemContext.Provider>
  );
}

export function AccordionTrigger({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const itemCtx = useContext(AccordionItemContext);
  const id = useId();
  if (!itemCtx) throw new Error("AccordionTrigger must be used within an AccordionItem");

  return (
    <button
      type="button"
      onClick={itemCtx.toggle}
      aria-expanded={itemCtx.isOpen}
      aria-controls={id}
      className={cn("flex w-full items-center justify-between gap-2", className)}
    >
      {children}
      <ChevronDown
        className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-200", itemCtx.isOpen && "rotate-180")}
      />
    </button>
  );
}

export function AccordionContent({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const itemCtx = useContext(AccordionItemContext);
  const id = useId();
  if (!itemCtx) throw new Error("AccordionContent must be used within an AccordionItem");
  if (!itemCtx.isOpen) return null;

  return (
    <div id={id} className={className}>
      {children}
    </div>
  );
}
