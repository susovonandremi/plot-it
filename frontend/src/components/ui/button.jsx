import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
     "inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-semibold ring-offset-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-95",
     {
          variants: {
               variant: {
                    default: "bg-sky-500 text-white hover:bg-sky-600 shadow-sm hover:shadow-md",
                    destructive: "bg-red-600 text-white hover:bg-red-700",
                    outline: "border-2 border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300 text-slate-700",
                    secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200",
                    ghost: "hover:bg-slate-100 hover:text-slate-900",
                    link: "text-sky-500 underline-offset-4 hover:underline",
               },
               size: {
                    default: "h-12 px-6 py-3",
                    sm: "h-9 rounded-md px-3",
                    lg: "h-14 rounded-md px-8",
                    icon: "h-10 w-10",
               },
          },
          defaultVariants: {
               variant: "default",
               size: "default",
          },
     }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
     const Comp = asChild ? Slot : "button"
     return (
          <Comp
               className={cn(buttonVariants({ variant, size, className }))}
               ref={ref}
               {...props}
          />
     )
})
Button.displayName = "Button"

export { Button, buttonVariants }
