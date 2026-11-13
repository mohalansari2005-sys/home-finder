import { Toaster as Sonner, type ToasterProps } from "sonner"

// No theme provider in this app: sonner follows prefers-color-scheme.
const Toaster = ({ ...props }: ToasterProps) => (
  <Sonner
    theme="system"
    dir="rtl"
    position="top-center"
    className="toaster group"
    style={
      {
        "--normal-bg": "var(--popover)",
        "--normal-text": "var(--popover-foreground)",
        "--normal-border": "var(--border)",
        "--border-radius": "var(--radius)",
      } as React.CSSProperties
    }
    {...props}
  />
)

export { Toaster }
