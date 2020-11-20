module.exports = {
  root: true,

  env: {
    node: true
  },

  extends: [
    "plugin:vue/recommended",
    "eslint:recommended",
    "prettier/vue",
    "plugin:prettier/recommended",
    "plugin:vue/essential",
    "@vue/prettier",
    "@vue/typescript/recommended",
    "@vue/prettier/@typescript-eslint"
  ],

  rules: {
    "vue/component-name-in-template-casing": ["error", "PascalCase"],
    "no-console": process.env.NODE_ENV === "production" ? "warn" : "off",
    "no-debugger": process.env.NODE_ENV === "production" ? "warn" : "off"
  },

  globals: {
    $nuxt: true
  },

  parserOptions: {
    parser: "babel-eslint"
  }
};
