/* File   : eslint.config.mjs                                              */
/* Purpose: Configuration for the VSCode ESLint extension and code linting */

import js from "@eslint/js";
import compat from "eslint-plugin-compat";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    plugins: {
      compat: compat,                  /* Browser compatibility checking plugin  */
    },
    languageOptions: {
      ecmaVersion: 2020,               /* Set syntax level to ECMAScript 2020      */
      sourceType : "module",           /* Enable modern import/export module logic */
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      "no-unused-vars": ["warn", {
          "argsIgnorePattern": "^_",   /* Ignore arguments starting with underscore*/
          "varsIgnorePattern": "^_"    /* Ignore variables starting with underscore*/
      }],
      "semi": ["error", "always"],     /* Require semicolons at the end            */
      "no-console"   : "off",          /* Set to off/error for console.log usage   */
      "compat/compat": "error",        /* Enforce browser compatibility checks     */
    },
  },
];
