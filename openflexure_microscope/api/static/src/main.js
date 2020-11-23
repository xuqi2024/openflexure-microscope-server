import { createApp } from "vue";
import App from "./App.vue";
import mitt from "mitt";
import store from "./store";
import mixin from "./mixin";
import UIkit from "uikit";
import VueFriendlyIframe from "vue-friendly-iframe";
import { ObserveVisibility } from "vue-observe-visibility";

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

const emitter = mitt();
let app = createApp(App);

// Use Friendly Iframe module
app.use(VueFriendlyIframe);
// Use visibility observer
// Hacky Vue 3 fix, see https://github.com/Akryum/vue-observe-visibility/issues/219
app.directive("observe-visibility", {
  beforeMount: (el, binding, vnode) => {
    vnode.context = binding.instance;
    ObserveVisibility.bind(el, binding, vnode);
  },
  update: ObserveVisibility.update,
  unmounted: ObserveVisibility.unbind
});

// Use Vuex store
app.use(store);
// Apply global mixin
app.mixin(mixin);
// Attach our global mitt emitter
app.config.globalProperties.$emitter = emitter;
// Mount the app
app.mount("#app");
