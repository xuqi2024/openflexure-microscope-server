<template>
  <div
    id="app"
    class="uk-height-1-1 uk-margin-remove uk-padding-remove"
    :class="handleTheme"
  >
    <loadingContent v-if="!$store.getters.ready" />
    <div v-if="$store.getters.ready" id="tour-header"></div>
    <appContent v-if="$store.getters.ready" />
    <v-tour
      v-show="$store.getters.ready"
      name="guidedTour"
      :steps="tourSteps"
      :callbacks="tourCallbacks"
      :options="{ highlight: true }"
    ></v-tour>
  </div>
</template>

<script>
// Import components
import appContent from "./components/appContent.vue";
import loadingContent from "./components/loadingContent.vue";

import axios from "axios";

// Key Codes
const keyCodes = {
  pgup: 33,
  pgdn: 34,
  left: 37,
  up: 38,
  right: 39,
  down: 40,
  enter: 13,
  esc: 27,
  shift: 16,
  alt: 18,
  t: 84
};

// Export main app
export default {
  name: "App",

  components: {
    appContent,
    loadingContent
  },

  data: function() {
    return {
      appAvailable: false,
      keysDown: {},
      systemDark: undefined,
      themeObserver: undefined,
      tourCallbacks: {
        onStop: () => {
          this.setLocalStorageObj("completedTour", true);
        }
      }
    };
  },

  computed: {
    isSystemDark: function() {
      if (
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
      ) {
        return true;
      } else {
        return false;
      }
    },
    handleTheme: function() {
      var isDark = false;
      if (this.$store.state.globalSettings.appTheme == "dark") {
        isDark = true;
      } else if (this.$store.state.globalSettings.appTheme == "system") {
        if (this.systemDark) {
          isDark = true;
        }
      }
      return {
        "uk-light": isDark,
        "uk-background-secondary": isDark
      };
    },
    tourSteps: function() {
      return [
        {
          target: "#tour-header", // We're using document.querySelector() under the hood
          header: {
            title: "Welcome to the OpenFlexure Microscope"
          },
          content: `Click Next to learn how to use your microscope`,
          params: {
            placement: "bottom"
          }
        },
        {
          target: "#gallery-tab-icon",
          header: {
            title: "Capture gallery"
          },
          content: `View and download your microscope images from the gallery tab`
        },
        {
          target: "#navigate-tab-icon",
          header: {
            title: "Navigate around your sample"
          },
          content: `Move your microscope stage and perform autofocus from the navigate tab`
        },
        {
          target: "#capture-tab-icon",
          header: {
            title: "Capture microscope images"
          },
          content: `Take images and simple tile scans from the capture tab`
        },
        {
          target: "#settings-tab-icon",
          header: {
            title: "Change settings"
          },
          content: `Change app and microscope settings, including microscope calibration, from the settings tab`
        },
        {
          target: "#extension-tab-divider",
          header: {
            title: "Microscope extensions"
          },
          content: `Extensions installed on your microscope will appear below this line`
        }
      ];
    }
  },

  mounted() {
    // Query CSS dark theme preference
    var mql = window.matchMedia("(prefers-color-scheme: dark)");
    // Check for system dark theme when mounted
    if (mql.matches) {
      this.systemDark = true;
    }
    // Create a theme observer to watch for changes
    this.themeObserver = mql.addListener(e => {
      if (e.matches) {
        this.systemDark = true;
      } else {
        this.systemDark = false;
      }
    });
    // Check connection to API
    this.checkConnection();
    // Handle guided tour
    // If the user has already completed or skipped the guided tour
    // TODO: Only run this if connected to the API
    var completedTour = this.getLocalStorageObj("completedTour") || false;
    if (!completedTour) {
      this.$tours["guidedTour"].start();
    }
  },

  created: function() {
    window.addEventListener("beforeunload", this.handleExit);
    // Key events
    window.addEventListener("keydown", this.keyDownMonitor);
    window.addEventListener("keyup", this.keyUpMonitor);
    window.addEventListener("wheel", this.wheelMonitor);
    // Watch for origin changes
    this.unwatchOriginFunction = this.$store.watch(
      (state, getters) => {
        return getters.uriV2;
      },
      uriV2 => {
        this.checkConnection();
        console.log(uriV2);
      }
    );
  },

  beforeDestroy: function() {
    // Disconnect the theme observer
    if (this.themeObserver) {
      this.themeObserver.disconnect();
    }
    // Remove key listeners
    window.removeEventListener("keydown", this.keyDownMonitor);
    window.removeEventListener("keyup", this.keyUpMonitor);
    window.removeEventListener("wheel", this.wheelMonitor);
    // Remove origin watcher
    this.unwatchOriginFunction();
  },

  methods: {
    checkConnection: function() {
      var uriV2 = this.$store.getters.uriV2;
      this.$store.commit("changeWaiting", true);
      axios
        .get(uriV2)
        .then(() => {
          this.$store.commit("setConnected");
          this.$store.commit("setErrorMessage", null);
        })
        .catch(error => {
          this.$store.commit("setErrorMessage", error);
        })
        .finally(() => {
          this.$store.commit("changeWaiting", false);
        });
    },

    handleExit: function() {
      console.log("Triggered beforeunload");
      this.$root.$emit("globalTogglePreview", false);
    },

    // Handle global mouse wheel events to be associated with navigation
    wheelMonitor: function(event) {
      // Only capture scroll if the event target's parent contains the "scrollTarget" class
      if (
        event.target.parentNode.classList.contains("scrollTarget") ||
        event.target.classList.contains("scrollTarget")
      ) {
        var z_rel = event.deltaY / 100;
        // Emit a signal to move, acted on by panelNavigate.vue
        this.$root.$emit("globalMoveStepEvent", 0, 0, z_rel, false);
      }
    },

    // Handle global key press events to be associated with navigation
    keyDownMonitor: function(event) {
      this.keysDown[event.keyCode] = true; //Add key to array

      // Convert keyCode dict into a list of key codes
      var keyCodeList = Object.keys(keyCodes).map(function(key) {
        return keyCodes[key];
      });

      if (
        // If not inside an element we want to ignore
        !(event.target instanceof HTMLInputElement) &&
        !event.target.classList.contains("lightbox-link") &&
        // If it's a recognised key
        keyCodeList.includes(event.keyCode)
      ) {
        this.navigateKeyHandler(keyCodes);
        this.captureKeyHandler(keyCodes);
        this.letterKeyHandler(keyCodes);
      }
    },

    keyUpMonitor: function(event) {
      delete this.keysDown[event.keyCode]; //Remove key from array
    },

    navigateKeyHandler: function(keyCodes) {
      const moveKeys = [
        keyCodes.left,
        keyCodes.right,
        keyCodes.up,
        keyCodes.down,
        keyCodes.pgup,
        keyCodes.pgdn
      ];

      if (
        moveKeys.some(r => Object.keys(this.keysDown).includes(r.toString()))
      ) {
        // Calculate movement array
        var x_rel = 0;
        var y_rel = 0;
        var z_rel = 0;
        if (keyCodes.left in this.keysDown) {
          x_rel = x_rel + 1;
        }
        if (keyCodes.right in this.keysDown) {
          x_rel = x_rel - 1;
        }
        if (keyCodes.up in this.keysDown) {
          y_rel = y_rel + 1;
        }
        if (keyCodes.down in this.keysDown) {
          y_rel = y_rel - 1;
        }
        if (keyCodes.pgup in this.keysDown) {
          z_rel = z_rel - 1;
        }
        if (keyCodes.pgdn in this.keysDown) {
          z_rel = z_rel + 1;
        }
        // Make a position request
        // Emit a signal to move, acted on by panelNavigate.vue
        this.$root.$emit("globalMoveStepEvent", x_rel, y_rel, z_rel);
      }
    },

    captureKeyHandler: function(keyCodes) {
      if (keyCodes.shift in this.keysDown && keyCodes.enter in this.keysDown) {
        console.log("Capturing");
        this.$root.$emit("globalCaptureEvent");
      }
    },

    letterKeyHandler: function(keyCodes) {
      if (keyCodes.alt in this.keysDown && keyCodes.t in this.keysDown) {
        this.$tours["guidedTour"].start();
      }
    }
  }
};
</script>

<style lang="less">
// Basic UIkit CSS
@import "../node_modules/uikit/src/less/uikit.less";
// Custom UIkit CSS modifications
@import "./assets/less/theme.less";

// We override the custom-electron-titlebar z-index
// UIKit lightbox must be able to draw over the titlebar
// as it currently always spawns at the root of the DOM
.titlebar,
.titlebar > * {
  z-index: 1000 !important;
}

#app {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: left;
  height: 100%;
}

body,
html {
  height: 100%;
  overflow: hidden;
}

.uk-disabled {
  pointer-events: none;
  opacity: 0.4;
}

.control-component {
  overflow-y: auto;
  overflow-x: hidden;
  width: 300px;
  height: 100%;
  padding: 0;
  background-color: rgba(180, 180, 180, 0.03);
  border-width: 0 1px 0 0;
  border-style: solid;
  border-color: rgba(180, 180, 180, 0.25);
}

.view-component {
  overflow-y: auto;
  overflow-x: hidden;
  height: 100%;
  padding: 0;
}

.section-content {
  padding: 0;
  height: 100%;
}

// Style tour
.v-tour__target--highlighted {
  box-shadow: 0px 40px 200px 30px rgba(0, 0, 0, 0.5),
    0px 0px 0px 4px rgba(128, 128, 128, 0.5) !important;
  border-radius: 5px;
  opacity: 100% !important;
  pointer-events: none !important;
}

.v-step {
  background: @global-primary-background !important;
}

.v-step__header {
  background-color: darken(@global-primary-background, 7%) !important;
}

.v-step__button {
  font-size: 0.9rem !important;
}

// Change step arrow colour
// This is awful and hacky and makes me sad, but needs must
.v-step .v-step__arrow {
  border-color: darken(@global-primary-background, 7%) !important;
  &--dark {
    border-color: darken(@global-primary-background, 7%) !important;
  }
}

.v-step[x-placement^="top"] .v-step__arrow {
  border-left-color: transparent !important;
  border-right-color: transparent !important;
  border-bottom-color: transparent !important;
}

.v-step[x-placement^="bottom"] .v-step__arrow {
  border-left-color: transparent !important;
  border-right-color: transparent !important;
  border-top-color: transparent !important;
}

.v-step[x-placement^="right"] .v-step__arrow {
  border-left-color: transparent !important;
  border-top-color: transparent !important;
  border-bottom-color: transparent !important;
}

.v-step[x-placement^="left"] .v-step__arrow {
  border-top-color: transparent !important;
  border-right-color: transparent !important;
  border-bottom-color: transparent !important;
}
</style>
