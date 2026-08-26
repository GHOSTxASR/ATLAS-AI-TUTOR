import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

/**
 * The point of this config is `react-hooks/exhaustive-deps`.
 *
 * `tsc --noEmit` was standing in for a linter, and a typechecker cannot see a
 * missing hook dependency. Two real bugs shipped because of that: the graph's
 * physics effect read `simNodes` but did not list it, so whether the layout ran
 * at all depended on a race, and a callback it used was neither memoised nor
 * declared. Both are exactly what this rule reports.
 */
export default tseslint.config(
  {
    ignores: ["dist", "coverage", "node_modules", "*.config.js", "*.config.ts"],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.es2021 },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,

      // The rule this whole config exists for. An error, not a warning:
      // a warning is a thing everyone scrolls past.
      "react-hooks/exhaustive-deps": "error",

      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],

      // Unused code is noise a reader has to rule out. Underscore-prefixed
      // names are the documented way to say "deliberately ignored".
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],

      // This codebase catches provider errors as `any` in a lot of places to
      // read `err.response.data`. Worth tightening eventually, but turning it
      // into an error today would bury the hook findings under dozens of
      // unrelated ones.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  {
    // Tests reach for globals and loose types by nature.
    files: ["**/*.test.{ts,tsx}", "src/test/**"],
    languageOptions: { globals: { ...globals.node } },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
);
