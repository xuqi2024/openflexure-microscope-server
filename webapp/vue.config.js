const ShebangPlugin = require('webpack-shebang-plugin');

module.exports = {
  configureWebpack: {
    plugins: [
      new ShebangPlugin()
    ]
  },
  outputDir: "../openflexure_microscope/api/static/dist"
};
