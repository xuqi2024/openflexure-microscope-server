<template>
  <div
    id="app"
    class="uk-height-1-1 uk-margin-remove uk-padding-remove"
    :class="handleTheme"
  >
    <loadingContent v-if="!$store.getters.ready" />
    <appContent v-if="$store.getters.ready" />
    <!-- Runtime modals -->
    <div
      id="modal-center"
      ref="keyboardManualModal"
      class="uk-flex-top"
      uk-modal
    >
      <div class="uk-modal-dialog uk-modal-body uk-margin-auto-vertical">
        <button class="uk-modal-close-default" type="button" uk-close></button>
        <div
          v-for="shortcut in keyboardManual"
          :key="shortcut.shortcut"
          class="uk-margin-small"
          uk-grid
        >
          <div class="uk-width-small">{{ shortcut.shortcut }}</div>
          <div class="uk-width-expand">{{ shortcut.description }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// Import components
import appContent from "./components/appContent.vue";
import loadingContent from "./components/loadingContent.vue";

import axios from "axios";
var Mousetrap = require("mousetrap");

Mousetrap.prototype.stopCallback = function(e, element) {
  // if the element has the class "mousetrap" then no need to stop
  if ((" " + element.className + " ").indexOf(" mousetrap ") > -1) {
    return false;
  }

  // if we're in a lightbox, stop mousetrap
  if (element.classList.contains("lightbox-link")) {
    return true;
  }

  // stop for input, select, and textarea
  return (
    element.tagName == "INPUT" ||
    element.tagName == "SELECT" ||
    element.tagName == "TEXTAREA" ||
    (element.contentEditable && element.contentEditable == "true")
  );
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
      arrowKeysDown: {},
      keyboardManual: [],
      systemDark: undefined,
      themeObserver: undefined
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
      if (this.$store.state.appTheme == "dark") {
        isDark = true;
      } else if (this.$store.state.appTheme == "system") {
        if (this.systemDark) {
          isDark = true;
        }
      }
      return {
        "uk-light": isDark,
        "uk-background-secondary": isDark
      };
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
  },

  created: function() {
    window.addEventListener("beforeunload", this.handleExit);
    // Scrollwheel listener
    window.addEventListener("wheel", this.wheelMonitor);
    // Watch for origin changes
    this.unwatchOriginFunction = this.$store.watch(
      (state, getters) => {
        return getters.uriV2;
      },
      () => {
        this.checkConnection();
      }
    );

    // Keyboard shortcuts
    Mousetrap.bind("?", () => {
      this.toggleModalElement(this.$refs["keyboardManualModal"]); // Calls the mixin
    });

    // Arrow keys
    Mousetrap.bind(
      ["up", "down", "left", "right"],
      event => {
        this.arrowKeysDown[event.keyCode] = true; //Add key to array
        this.navigateKeyHandler();
      },
      "keydown"
    );
    Mousetrap.bind(
      ["up", "down", "left", "right"],
      event => {
        delete this.arrowKeysDown[event.keyCode]; //Remove key from array
      },
      "keyup"
    );
    this.keyboardManual.push({
      shortcut: "←↑→↓",
      description: "Move the microscope stage"
    });

    // Focus keys
    Mousetrap.bind("pageup", () => {
      this.$emitter.emit("globalMoveStepEvent", 0, 0, 1);
    });
    Mousetrap.bind("pagedown", () => {
      this.$emitter.emit("globalMoveStepEvent", 0, 0, -1);
    });
    this.keyboardManual.push({
      shortcut: "pgup / pgdn",
      description: "Move the microscope focus"
    });

    // Capture
    Mousetrap.bind("c", () => {
      this.$emitter.emit("globalCaptureEvent");
    });
    this.keyboardManual.push({
      shortcut: "c",
      description: "Take a capture"
    });

    // Autofocus
    Mousetrap.bind("a", () => {
      this.$emitter.emit("globalFastAutofocusEvent");
    });
    this.keyboardManual.push({
      shortcut: "a",
      description: "Fast autofocus"
    });

    // Increment/decrement tab
    Mousetrap.bind("shift+down", () => {
      this.$emitter.emit("globalIncrementTab");
    });
    Mousetrap.bind("shift+up", () => {
      this.$emitter.emit("globalDecrementTab");
    });
    this.keyboardManual.push({
      shortcut: "shift+↑ / shift+↓",
      description: "Switch tab"
    });
  },

  beforeUnmount: function() {
    // Disconnect the theme observer
    if (this.themeObserver) {
      this.themeObserver.disconnect();
    }
    // Remove scrollwheel listener
    window.removeEventListener("wheel", this.wheelMonitor);
    // Remove origin watcher
    this.unwatchOriginFunction();
    // Remove key listeners
    Mousetrap.reset();
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
      this.$emitter.emit("globalTogglePreview", false);
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
        this.$emitter.emit("globalMoveStepEvent", 0, 0, z_rel, false);
      }
    },

    navigateKeyHandler: function() {
      // Calculate movement array
      var x_rel = 0;
      var y_rel = 0;
      var z_rel = 0;
      if (37 in this.arrowKeysDown) {
        x_rel = x_rel + 1;
      }
      if (39 in this.arrowKeysDown) {
        x_rel = x_rel - 1;
      }
      if (38 in this.arrowKeysDown) {
        y_rel = y_rel + 1;
      }
      if (40 in this.arrowKeysDown) {
        y_rel = y_rel - 1;
      }
      // Make a position request
      // Emit a signal to move, acted on by panelNavigate.vue
      this.$emitter.emit("globalMoveStepEvent", x_rel, y_rel, z_rel);
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
</style>
