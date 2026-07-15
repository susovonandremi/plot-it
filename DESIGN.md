---
name: PlotIt Architecture & Property Intelligence
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#bbc9cd'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#859397'
  outline-variant: '#3c494c'
  surface-tint: '#2fd9f4'
  primary: '#8aebff'
  on-primary: '#00363e'
  primary-container: '#22d3ee'
  on-primary-container: '#005763'
  inverse-primary: '#006877'
  secondary: '#45dfa4'
  on-secondary: '#003825'
  secondary-container: '#00bd85'
  on-secondary-container: '#00452e'
  tertiary: '#cfdef4'
  on-tertiary: '#233143'
  tertiary-container: '#b3c2d8'
  on-tertiary-container: '#415062'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#a2eeff'
  primary-fixed-dim: '#2fd9f4'
  on-primary-fixed: '#001f25'
  on-primary-fixed-variant: '#004e5a'
  secondary-fixed: '#68fcbf'
  secondary-fixed-dim: '#45dfa4'
  on-secondary-fixed: '#002114'
  on-secondary-fixed-variant: '#005137'
  tertiary-fixed: '#d4e4fa'
  tertiary-fixed-dim: '#b9c8de'
  on-tertiary-fixed: '#0d1c2d'
  on-tertiary-fixed-variant: '#39485a'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.02em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  sidebar-width: 280px
---

## Brand & Style

The brand personality is precise, technical, and authoritative, designed for architects, developers, and urban planners. It avoids the whimsical "magic" of consumer generators, instead focusing on the mathematical rigor of CAD software and property data analysis.

The visual style is a blend of **Grounded Minimalism** and **Technical Glassmorphism**. It draws inspiration from high-end architectural blueprints and dark-mode developer environments. Interfaces should feel like a sophisticated instrument—utilitarian but premium. Every element serves a functional purpose, with visual flourishes limited to data visualization and structural highlighting rather than decorative patterns.

## Colors

The palette is rooted in a deep, nocturnal base to reduce eye strain during long technical sessions.

- **Base Background:** `#0F172A` (Deep Slate) provides the foundation for the "Blueprint" aesthetic.
- **Accents:** Cyan (`#22D3EE`) is used for primary actions, active architectural lines, and selection states. Emerald (`#34D399`) is reserved for sustainable metrics and growth indicators.
- **Functional Colors:** Standardized Success, Warning, and Error colors are used for score indicators and validation logic.
- **Data Tints:** Use subtle shifts in slate and navy for container layering to maintain depth without breaking the dark-mode immersion.

## Typography

This design system uses a dual-font strategy to separate interface navigation from technical data.

- **Inter:** The primary workhorse for all UI elements, navigation, and prose. It provides high legibility in dark environments.
- **JetBrains Mono:** Used for all technical measurements, coordinate data, plot dimensions, and AI-generated scores. This reinforces the mathematical and CAD-centric nature of the product.
- **Scale:** Keep headings tight and compact. Use `label-caps` for metadata tags and axis labels to mimic architectural labeling conventions.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model. The sidebar and inspection panels are fixed-width to maintain data density, while the central viewport (the "Canvas") is fluid.

- **Grid:** Use a 4px baseline grid for all internal component spacing.
- **Canvas:** The main map/drawing area should occupy the maximum available space.
- **Margins:** Desktop views should maintain a 32px safe area from the screen edge for floating toolbars.
- **Reflow:** On mobile, the inspection panels collapse into a bottom sheet, and the sidebar becomes a hidden drawer to prioritize the visual data.

## Elevation & Depth

Hierarchy is established through **Tonal Layering** and **Subtle Glassmorphism**. 

1. **Surface Base:** Level 0 is the map or plot canvas (`#0F172A`).
2. **Fixed Panels:** Navigation and sidebars use Level 1 depth—slightly lighter than the base with a subtle 1px border (`#1E293B`).
3. **Floating Toolbars:** Use Level 2 glassmorphism. Background: `rgba(15, 23, 42, 0.7)` with a `20px` backdrop-blur and a subtle `0.5px` white inner stroke at 10% opacity.
4. **Modals:** Use high-contrast shadows—wide, diffused, and slightly tinted with Navy (`rgba(0, 0, 0, 0.5)`).

Avoid heavy dropshadows on static components; use borders to define structural lines, mimicking CAD software.

## Shapes

The shape language is **Soft (0.25rem)**. While modern, the design avoids overly bubbly or circular motifs to maintain its professional, engineered feel. 

- **Components:** Standard buttons and inputs use a 4px (`0.25rem`) radius.
- **Large Cards:** Use 8px (`0.5rem`) for property detail cards.
- **Exceptions:** Only circular elements allowed are status dots and avatar placeholders. All other elements should feel architectural and structured.

## Components

- **Buttons:** Primary buttons are Solid Cyan with black text for maximum contrast. Secondary buttons are ghost-style with a 1px slate border and monochrome text.
- **Input Fields:** Use "Underline-only" or "Thin Bordered" styles to mimic data entry forms. Use Mono font for numerical input.
- **Score Indicators:** Circular gauges or linear progress bars using the functional Success/Warning/Error colors. These should be high-vibrancy against the dark background.
- **Floating Toolbars:** Compact, segmented icon groups with glassmorphism backgrounds. Icons are 20px with 1.5px stroke weight.
- **Data Chips:** Small, square-edged labels with JetBrains Mono text. Backgrounds should be low-opacity versions of the accent colors (e.g., Cyan at 10% opacity).
- **Dimension Lines:** Use the primary Cyan color at 1px width with arrowheads for plot measurements.