import Vue from "vue";
import App from "./App.vue";
import store from "./store";
import UIkit from "uikit";
import VueTour from "vue-tour";
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

// Use vue-tour module
Vue.use(VueTour);

// Use Friendly Iframe module
Vue.use(VueFriendlyIframe);

// Use visibility observer
Vue.use(VueObserveVisibility);

Vue.config.productionTip = false;

Vue.mixin({
  methods: {
    async getConsumedThingFromURI(uri) {
      // Get a thing client, creatin it if necessary
      if (! (uri in store.state.wot.consumedThings) ) {
        await store.dispatch("wot/consumeThing", uri);
      }
      return store.state.consumedThings[uri];
    },
    async getConsumedThing(thing) {
      let baseUri = this.$store.state.baseUri;
      return await this.getConsumedThingFromURI(`${baseUri}/${thing}/`);
    },
    modalConfirm: function(modalText) {
      var context = this;

      // Stop GPU preview to show modal
      context.$root.$emit("globalTogglePreview", false);

      var showModal = function(resolve, reject) {
        UIkit.modal
          .confirm(modalText, { stack: true })
          .then(
            function() {
              resolve();
            },
            function() {
              reject();
            }
          )
          .finally(function() {
            // Reenable the GPU preview, if it was active before the modal
            if (context.$store.state.autoGpuPreview) {
              context.$root.$emit("globalTogglePreview", true);
            }
          });
      };
      return new Promise(showModal);
    },

    modalNotify: function(message, status = "success") {
      UIkit.notification({
        message: message,
        status: status
      });
    },

    modalDialog: function(title, message) {
      UIkit.modal.dialog(
        `
        <button class="uk-modal-close-default" type="button" uk-close></button>
        <div class="uk-modal-header">
          <h2 class="uk-modal-title">${title}</h2>
        </div>
        <div class="uk-modal-body">
          <p>${message}</p>
        </div>
      `,
        { stack: true }
      );
    },

    modalError: function(error) {
      var errormsg = this.getErrorMessage(error);
      this.$store.commit("setErrorMessage", errormsg);
      UIkit.notification({
        message: `${errormsg}`,
        status: "danger"
      });
    },

    getErrorMessage: function(error) {
      var errormsg = "";

      // If a response was obtained
      if (error.response) {
        // If the response is a nicely formatted JSON response from the server
        if (error.response.data.message) {
          errormsg = `${error.response.status}: ${error.response.data.message}`;
        }
        // If the response is just some generic error response
        else {
          errormsg = `${error.response.status}: ${error.response.data}`;
        }
        // If the error occured during the request
      } else if (error.request) {
        errormsg = `${error.message}`;
        // Everything else
      } else {
        errormsg = `${error.message}`;
      }
      return errormsg;
    },

    showModalElement: function(element) {
      UIkit.modal(element).show();
    },

    hideModalElement: function(element) {
      UIkit.modal(element).hide();
    },

    toggleModalElement: function(element) {
      UIkit.modal(element).toggle();
    },

    getLocalStorageObj: function(keyName) {
      if (localStorage.getItem(keyName)) {
        try {
          return JSON.parse(localStorage.getItem(keyName));
        } catch (e) {
          localStorage.removeItem(keyName);
          return null;
        }
      }
    },

    setLocalStorageObj: function(keyName, object) {
      const parsed = JSON.stringify(object);
      localStorage.setItem(keyName, parsed);
    }
  }
});

new Vue({
  store,
  render: h => h(App)
}).$mount("#app");
