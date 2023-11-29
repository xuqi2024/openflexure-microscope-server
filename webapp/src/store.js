import Vue from "vue";
import Vuex from "vuex";
import wotStoreModule from "./wot-client";

Vue.use(Vuex);

const moduleImjoy = {
  namespaced: true,
  state: () => ({
    tabs: [],
    openImageMenu: [],
    openScanMenu: []
  }),
  mutations: {
    addOpenImageItem(state, newItem) {
      state.openImageMenu.push(newItem);
    }, // TODO: add a mutation to remove items when plugins are unloaded
    addOpenScanItem(state, newItem) {
      state.openScanMenu.push(newItem);
    }, // TODO: add a mutation to remove items when plugins are unloaded
    clearMenus(state) {
      // This is primarily useful to reset the state in hot-reloads of
      // imjoyContent.vue
      state.openImageMenu = [];
      state.openScanMenu = [];
    },
    addTab(state, newItem) {
      // Add a tab to the list of ImJoy tabs
      state.tabs.push(newItem);
    },
    removeTab(state, tabToRemove) {
      const index = state.tabs.indexOf(tabToRemove);
      if (index > -1) {
        state.tabs.splice(index, 1);
      } else {
        console.warn(
          `Attempted to remove a non-existing ImJoy tab ${tabToRemove}`
        );
      }
    },
    /**
     * Set a parameter on the tab with a given id
     *
     * Payload should contain:
     *   tab: ID of the tab to modify (not window_id)
     *   key: name of the property to add/change
     *   value: value of the property to add/change
     */
    setTabProperty(state, payload) {
      let tab = payload.tab;
      let key = payload.key;
      let value = payload.value;
      state.tabs = state.tabs.map(t => {
        if (t.id === tab) {
          t[key] = value;
        }
        return t;
      });
    }
  },
  actions: {},
  getters: {}
};

function getOriginFromLocation() {
  // This will default to the same origin that's serving
  // the web app - but can be overridden by the URL.
  // See also devTools.vue which can change the origin.
  let url = new URL(window.location.href);
  let origin = url.searchParams.get("overrideOrigin");
  if (origin) {
    return origin;
  } else {
    return url.origin;
  }
}

export default new Vuex.Store({
  modules: {
    imjoy: moduleImjoy,
    wot: wotStoreModule
  },
  state: {
    origin: getOriginFromLocation(),
    available: false,
    waiting: false,
    error: "",
    disableStream: false,
    autoGpuPreview: false,
    trackWindow: true,
    IHIEnabled: false,
    imjoyEnabled: false,
    galleryEnabled: true,
    appTheme: "system",
    activeStreams: {}
  },

  mutations: {
    changeOrigin(state, origin) {
      state.origin = origin;
    },
    changeWaiting(state, waiting) {
      state.waiting = waiting;
    },
    changeDisableStream(state, disabled) {
      state.disableStream = disabled;
    },
    changeAutoGpuPreview(state, enabled) {
      state.autoGpuPreview = enabled;
    },
    changeTrackWindow(state, enabled) {
      state.trackWindow = enabled;
    },
    changeAppTheme(state, theme) {
      state.appTheme = theme;
    },
    changeIHIEnabled(state, enabled) {
      state.IHIEnabled = enabled;
    },
    changeImjoyEnabled(state, enabled) {
      if (process.env.VUE_APP_ENABLE_IMJOY === "true") {
        state.imjoyEnabled = enabled;
      } else {
        state.imjoyEnabled = false;
        if (enabled)
          console.warn(
            "Attempted to enable ImJoy, but it's disabled by VUE_APP_ENABLE_IMJOY."
          );
      }
    },
    changeGalleryEnabled(state, enabled) {
      state.galleryEnabled = enabled;
    },
    resetState(state) {
      state.waiting = false;
      state.available = false;
      state.error = null;
    },
    setConnected(state) {
      state.waiting = false;
      state.available = true;
    },
    setErrorMessage(state, msg) {
      state.error = msg;
    },
    addStream(state, id) {
      state.activeStreams[id] = true;
    },
    removeStream(state, id) {
      state.activeStreams[id] = false;
    }
  },

  actions: {},

  getters: {
    baseUri: state => state.origin,
    ready: state => state.available
  }
});
