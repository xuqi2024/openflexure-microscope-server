# OpenFlexure Microscope JS Client

## Key info

* Vue.js web application providing a graphical interface for the OFM
* Once built, will be served by the API server from the host root on port 5000

* See [openflexure-microscope-server/README.md](https://gitlab.com/openflexure/openflexure-microscope-server/-/blob/master/README.md) for details on local installation and building

# Developer guidelines

## Creating releases

* JS client is coupled to the API, and so are no longer separately built and deployed.
* See [openflexure-microscope-server/README.md](https://gitlab.com/openflexure/openflexure-microscope-server/-/blob/master/README.md) for details on creating new releases

## Installing

* Install Node.js (and npm)
* Install dependencies with `npm install`
* Node v18 changes SSL, and so you need `$env:NODE_OPTIONS = "--openssl-legacy-provider"` on Windows or `export NODE_OPTIONS=--openssl-legacy-provider` on Linux/MacOS for compatibility.
* Build the static web app with `npm run build`
* Serve a development version with `npm run serve`

We generally run this on the Raspberry Pi (as that is where the Webapp is hosted). If this isn't suitable - for example, if you can't install Node on your microscope due to version conflicts or no internet connection - you can build it on your computer instead, and then copy over the contents of `..\src\openflexure_microscope_server\static` to your Pi (using scp or another file transfer method).

## VS Code and ESLint

To prevent the editor from interfering with ESLint, add to your project `settings.json`:

```json
{
    "editor.tabSize": 2,
    "cSpell.enabled": false,
    "eslint.validate": ["vue","javascript", "javascriptreact"],
    "editor.formatOnSave": false,
    "vetur.validation.template": false,
    "editor.codeActionsOnSave": {
        "source.fixAll.eslint": true
    }
}
```