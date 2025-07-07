import Vue from "vue";
import Vuex from "vuex";
import wotStoreModule from "./wot-client";

Vue.use(Vuex);

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
    galleryEnabled: true,
    appTheme: "system",
    activeStreams: {},
    microscopeHostname: ""
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
    },
    changeMicroscopeHostname(state, value) {
      state.microscopeHostname = value;
    }
  },

  actions: {},

  getters: {
    baseUri: state => state.origin,
    ready: state => state.available
  }
});
