# OpenFlexure Microscope JS Client

## Developer notes

### VS Code and ESLint

To prevent the editor from interfering with ESLint, add to your project `settings.json `:

```
{
    "editor.tabSize": 2,
    "cSpell.enabled": false,
    "eslint.validate": [{
            "language": "vue",
            "autoFix": true
        },
        {
            "language": "javascript",
            "autoFix": true
        },
        {
            "language": "javascriptreact",
            "autoFix": true
        }
    ],
    "eslint.autoFixOnSave": true,
    "editor.formatOnSave": false,
    "vetur.validation.template": false
}
```