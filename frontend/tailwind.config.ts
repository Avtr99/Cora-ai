import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";
import { BRAND, SEMANTIC, CHART, KPI, GAUGE, SDG_COLORS } from './src/lib/colors';

export default {
	content: [
		"./pages/**/*.{ts,tsx}",
		"./components/**/*.{ts,tsx}",
		"./app/**/*.{ts,tsx}",
		"./src/**/*.{ts,tsx}",
	],
	prefix: "",
	theme: {
		container: {
			center: true,
			padding: '2rem',
			screens: {
				'2xl': '1400px'
			}
		},
		fontFamily: {
			sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
			poppins: ['Poppins', 'sans-serif'],
			inter: ['Inter', 'sans-serif'],
		},
		extend: {
			boxShadow: {
				'xs':         'var(--shadow-xs)',
				'card':       'var(--shadow-card)',
				'card-md':    'var(--shadow-card-md)',
				'card-sm':    'var(--shadow-card-sm)',
				'bottom-bar': 'var(--shadow-bottom-bar)',
				'modal':      'var(--shadow-modal)',
				'scroll-btn': 'var(--shadow-scroll-btn)',
			},
			minHeight: {
				'touch':    '44px',
				'touch-lg': '72px',
			},
			fontSize: {
				'2xs': ['10px', { lineHeight: '14px' }],
			},
			letterSpacing: {
				'widest': '0.14em',
			},
			width: {
				'4.5': '1.125rem',
			},
			height: {
				'4.5': '1.125rem',
			},
			colors: {
				border: 'hsl(var(--border))',
				input: 'hsl(var(--input))',
				ring: 'hsl(var(--ring))',
			focus: 'hsl(var(--focus))',
				background: 'hsl(var(--background))',
				foreground: 'hsl(var(--foreground))',
				primary: {
					DEFAULT: 'hsl(var(--primary))',
					foreground: 'hsl(var(--primary-foreground))'
				},
				// ── Canonical design-system palette ──────────────────────────
				// Surface (backgrounds)
				// surface-page  : #F7F8FB  cool-tinted page-level bg
				// surface-base  : #FAFAFA  near-white panels, table headers
				// surface-card  : #FFFFFF  pure-white cards
				// surface-subtle: #F3F4F6  dividers, row-alternation
				// Borders
				// border-ui     : #E5E7EB  standard borders (absorbs #E5E5E5, #ECECF0, #E7E7E7)
				// Text
				// text-primary  : #171717  headings (absorbs #1F1F1F, #1a1a1a)
				// text-secondary: #525252  body text (absorbs #5B5B7A, #374151, #4B5563)
				// text-muted    : #6B7280  labels/captions (absorbs #666666, #99A1AF, #9CA3AF)
				// Brand purple
				// brand.primary : #403D85  dark buttons
				// brand.secondary: #6F4ECB vibrant accent / hover
				// brand.link    : #4A2AA3  nav links (absorbs #5D4A9F)
				// brand.hover   : #3a2182  hover for dark brand elements
				// ─────────────────────────────────────────────────────────────
				'surface-page':   '#F7F8FB',
				'surface-base':   '#FAFAFA',
				'surface-card':   '#FFFFFF',
				'surface-subtle': '#F3F4F6',
				'border-ui':      '#E5E7EB',
				'text-primary':   '#171717',
				'text-secondary': '#525252',
				'text-muted':     '#6B7280',
				// Chart colors
				'chart-retired':  '#4B5563', // gray-600 for retired credits bar
				brand: {
					// Numeric scale — direct hex from colors.ts (single source of truth)
					// Usage: bg-brand-50, bg-brand-100, text-brand-500, border-brand-200, etc.
					50:  BRAND.primary50,   // '#FAF5FF'
					100: BRAND.primary100,  // '#F3E8FF'
					200: BRAND.primary200,  // '#E9D5FF'
					500: BRAND.primary500,  // '#6F4ECB'
					700: BRAND.primary700,  // '#4A2AA3'
					900: BRAND.primary900,  // '#403D85'
					// Semantic aliases — CSS-variable-backed for theme switching
					primary:   'hsl(var(--brand-primary))',
					secondary: 'hsl(var(--brand-secondary))',
					link:      'hsl(var(--brand-link))',
					hover:     'hsl(var(--brand-hover))',
				},
				// Semantic status colors (success / error / warning / info)
				semantic: {
					success: {
						bg:          SEMANTIC.success.bg,
						text:        SEMANTIC.success.text,
						border:      SEMANTIC.success.border,
						icon:        SEMANTIC.success.icon,
						iconBg:      SEMANTIC.success.iconBg,
						button:      SEMANTIC.success.button,
						buttonHover: SEMANTIC.success.buttonHover,
					},
					error: {
						bg:          SEMANTIC.error.bg,
						text:        SEMANTIC.error.text,
						border:      SEMANTIC.error.border,
						icon:        SEMANTIC.error.icon,
						iconBg:      SEMANTIC.error.iconBg,
						button:      SEMANTIC.error.button,
						buttonHover: SEMANTIC.error.buttonHover,
					},
					warning: {
						bg:          SEMANTIC.warning.bg,
						text:        SEMANTIC.warning.text,
						border:      SEMANTIC.warning.border,
						icon:        SEMANTIC.warning.icon,
						iconBg:      SEMANTIC.warning.iconBg,
						button:      SEMANTIC.warning.button,
						buttonHover: SEMANTIC.warning.buttonHover,
					},
					info: {
						bg:          SEMANTIC.info.bg,
						text:        SEMANTIC.info.text,
						border:      SEMANTIC.info.border,
						icon:        SEMANTIC.info.icon,
						iconBg:      SEMANTIC.info.iconBg,
						button:      SEMANTIC.info.button,
						buttonHover: SEMANTIC.info.buttonHover,
					},
				},
				// SDG badge colors
				sdg: SDG_COLORS,
				// Data-visualization colors
				chart: {
					household:   CHART.household,
					agriculture: CHART.agriculture,
					renewable:   CHART.renewable,
					redd:        CHART.redd,
				},
				kpi: {
					reduction: KPI.reduction,
					removal:   KPI.removal,
					other:     KPI.other,
				},
				gauge: {
					retired:   GAUGE.retired,
					remaining: GAUGE.remaining,
				},
				secondary: {
					DEFAULT: 'hsl(var(--secondary))',
					foreground: 'hsl(var(--secondary-foreground))'
				},
				destructive: {
					DEFAULT: 'hsl(var(--destructive))',
					foreground: 'hsl(var(--destructive-foreground))'
				},
				muted: {
					DEFAULT: 'hsl(var(--muted))',
					foreground: 'hsl(var(--muted-foreground))'
				},
				accent: {
					DEFAULT: 'hsl(var(--accent))',
					foreground: 'hsl(var(--accent-foreground))'
				},
				popover: {
					DEFAULT: 'hsl(var(--popover))',
					foreground: 'hsl(var(--popover-foreground))'
				},
				card: {
					DEFAULT: 'hsl(var(--card))',
					foreground: 'hsl(var(--card-foreground))'
				},
				sidebar: {
					DEFAULT: 'hsl(var(--sidebar-background))',
					foreground: 'hsl(var(--sidebar-foreground))',
					primary: 'hsl(var(--sidebar-primary))',
					'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
					accent: 'hsl(var(--sidebar-accent))',
					'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
					border: 'hsl(var(--sidebar-border))',
					ring: 'hsl(var(--sidebar-ring))'
				}
			},
			borderRadius: {
				lg: 'var(--radius)',
				md: 'calc(var(--radius) - 2px)',
				sm: 'calc(var(--radius) - 4px)'
			},
			keyframes: {
				'accordion-down': {
					from: {
						height: '0'
					},
					to: {
						height: 'var(--radix-accordion-content-height)'
					}
				},
				'accordion-up': {
					from: {
						height: 'var(--radix-accordion-content-height)'
					},
					to: {
						height: '0'
					}
				}
			},
			animation: {
				'accordion-down': 'accordion-down 0.2s ease-out',
				'accordion-up': 'accordion-up 0.2s ease-out'
			}
		}
	},
	plugins: [tailwindcssAnimate],
} satisfies Config;
