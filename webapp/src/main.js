import Vue from "vue";
import App from "./App.vue";
import store from "./store";
import axios from "axios";
import UIkit from "uikit";
import VueTour from "vue-tour";
import VueFriendlyIframe from "vue-friendly-iframe";
import VueObserveVisibility from "vue-observe-visibility";

require("vue-tour/dist/vue-tour.css");

// Import MD icons
import "material-symbols/outlined.css";
import version from './version.js'

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
    app_version() {
      return version;
    },
    thingDescription(thing) {
      return this.$store.getters["wot/thingDescription"](thing);
    },
    thingAvailable(thing) {
      return this.$store.getters["wot/thingAvailable"](thing);
    },
    async readThingProperty(thing, property, silence_errors = false) {
      let url = this.$store.getters["wot/thingPropertyUrl"](
        thing,
        property,
        "readproperty",
        false
      );
      try {
        let response = await axios.get(url);
        return response.data;
      } catch (error) {
        if (!silence_errors) this.modalError(error);
        return undefined;
      }
    },
    async writeThingProperty(thing, property, value) {
      let url = this.$store.getters["wot/thingPropertyUrl"](
        thing,
        property,
        "writeproperty",
        false
      );
      // `false` fails because axios somehow eats it!
      // Other values should not be stringified or pydantic
      // can't parse them.
      if ((value === false) | (value === true)) {
        value = JSON.stringify(value);
      }
      await axios.put(url, value);
    },
    thingActionUrl(thing, action, allow_missing = false) {
      let url = this.$store.getters["wot/thingActionUrl"](
        thing,
        action,
        "invokeaction",
        allow_missing
      );
      return url;
    },
    modalConfirm: function(modalText) {
      var context = this;

      // Stop GPU preview to show modal
      context.$root.$emit("globalTogglePreview", false);

      // force OK to be capitalised
      UIkit.modal.i18n = { ok: "OK", cancel: "Cancel" };

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
      console.log("Modal error:", error);
      UIkit.notification({
        message: `${errormsg}`,
        status: "danger"
      });
    },

    getErrorMessage: function(error) {
      // If a response was obtained, format it nicely and return it
      if (error.response) {
        // If the response is a nicely formatted JSON response from the server
        if (error.response.data.message) {
          return `${error.response.data.message}`;
        }
        if (error.response.data.detail) {
          return `${error.response.data.detail}`;
        }
        // If the response is just some generic error response
        if (error.response.data) {
          return `${error.response.data}`;
        }
        return `${error.response}`;
      }
      // If we have an error object with a message, use that
      if (error.message) return `${error.message}`;
      // Otherwise attempt to cast it to a string.
      return `${error}`;
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
