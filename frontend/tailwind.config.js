// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  // Use darkMode based on the 'html' element class (set manually or by OS preference)
  // Or use 'media' to rely solely on OS preference. 'class' gives more control.
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}", // Scan all JS/TS/JSX files in src
  ],
  theme: {
    extend: {
      // Define colors using your CSS variables for consistency
      // This allows using classes like `bg-primary-500`, `text-neutral-200`
      colors: {
        primary: {
          50: 'var(--primary-50)',
          100: 'var(--primary-100)',
          200: 'var(--primary-200)',
          300: 'var(--primary-300)',
          400: 'var(--primary-400)',
          500: 'var(--primary-500)',
          600: 'var(--primary-600)',
          700: 'var(--primary-700)',
          800: 'var(--primary-800)',
          900: 'var(--primary-900)',
          950: 'var(--primary-950)',
        },
        // Map neutral colors used in index.css to Tailwind names
        neutral: {
           DEFAULT: 'var(--bg-default)', // bg-neutral maps to bg-default
           50:  'var(--text-primary)',   // gray-50
           100: '#E5E7EB', // Approx gray-200 light mode for text contrast if needed
           200: 'var(--text-secondary)', // gray-300
           300: 'var(--text-tertiary)',  // gray-400
           400: 'var(--text-placeholder)', // gray-500
           500: 'var(--border-default)',  // gray-600
           600: 'var(--border-subtle)',   // gray-700
           700: 'var(--bg-elevated)',   // gray-800
           800: 'var(--bg-card)',       // gray-800 (same as elevated)
           900: 'var(--bg-default)',     // gray-900
        },
        // Map semantic colors
        success: 'var(--color-success)',
        error: 'var(--color-error)',
        warning: 'var(--color-warning)',
        info: 'var(--color-info)',
      },
      // You can extend other theme aspects like fonts, spacing, etc.
      fontFamily: {
        // Ensure 'Inter' is included if you use font-sans class
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
    },
  },
  plugins: [
    // Add any Tailwind plugins here (e.g., @tailwindcss/forms)
  ],
}