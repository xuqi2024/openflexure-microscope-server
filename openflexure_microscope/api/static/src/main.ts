import Vue from "vue";
import App from "./App.vue";
import store from "./store";
import GlobalMixin from "./mixin";
import UIkit from "uikit";
import VueTour from "vue-tour";
import LoadScript from "vue-plugin-load-script";
import VueFriendlyIframe from "vue-friendly-iframe";
import VueObserveVisibility from "vue-observe-visibility";

require("vue-tour/dist/vue-tour.css");

// Import MD icons
import "material-design-icons/iconfont/material-icons.css";

// UIKit overrides
UIkit.mixin(
  {
    data: {
      animation: false
    }
  },
  "accordion"
);

// Use load-script module
Vue.use(LoadScript);

// Use vue-tour module
Vue.use(VueTour);

// Use Friendly Iframe module
Vue.use(VueFriendlyIframe);

// Use visibility observer
Vue.use(VueObserveVisibility);

Vue.config.productionTip = false;

Vue.mixin(GlobalMixin);

new Vue({
  store,
  render: h => h(App)
}).$mount("#app");
