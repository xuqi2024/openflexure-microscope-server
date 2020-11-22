module.exports = {
  root: true,

  env: {
    node: true,
  },

  extends: [
    "plugin:vue/recommended",
    "eslint:recommended",
    "prettier/vue",
    "plugin:prettier/recommended",
    "@vue/typescript",
  ],

  rules: {
    "vue/component-name-in-template-casing": ["error", "PascalCase"],
    "no-console": process.env.NODE_ENV === "production" ? "warn" : "off",
    "no-debugger": process.env.NODE_ENV === "production" ? "warn" : "off",
  },

  globals: {
    $nuxt: true,
  },

  parserOptions: {
    parser: "@typescript-eslint/parser", // the typescript-parser for eslint, instead of tslint
    sourceType: "module", // allow the use of imports statements
    ecmaVersion: 2018, // allow the parsing of modern ecmascript
  },
};
