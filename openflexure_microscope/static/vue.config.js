var webpack = require("webpack");

module.exports = {
  configureWebpack: {
    plugins: [
      new webpack.DefinePlugin({
        "process.env": {
          PACKAGE: JSON.stringify(require("./package.json"))
        }
      })
    ]
  },

  publicPath: ""
};
