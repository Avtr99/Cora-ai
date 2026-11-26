import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config({ ignores: ["dist", "backup_gcp_backend"] }, {
  extends: [js.configs.recommended, ...tseslint.configs.recommended],
  files: ["**/*.{ts,tsx}"],
  languageOptions: {
    ecmaVersion: 2020,
    globals: globals.browser,
  },
  plugins: {
    "react-hooks": reactHooks,
    "react-refresh": reactRefresh,
  },
  rules: {
    ...reactHooks.configs.recommended.rules,
    // react-hooks v7 ships React Compiler-powered rules in `recommended` that
    // did not exist in v5. They flag long-standing, working patterns in this
    // codebase — keep them off so the lint gate matches the pre-upgrade surface.
    "react-hooks/set-state-in-effect": "off",
    "react-hooks/immutability": "off",
    "react-hooks/refs": "off",
    "react-hooks/incompatible-library": "off",
    "react-refresh/only-export-components": [
      "warn",
      { allowConstantExport: true },
    ],
    "@typescript-eslint/no-unused-vars": "off",
  },
});
