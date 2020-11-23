import Vuex from "vuex";

export default Vuex.createStore({
  state: {
    origin: window.location.origin,
    available: false,
    waiting: false,
    error: "",
    disableStream: false,
    autoGpuPreview: false,
    trackWindow: true,
    IHIEnabled: false,
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
    resetState(state) {
      state.waiting = false;
      state.available = false;
      state.error = null;
    },
    setConnected(state) {
      state.waiting = false;
      state.available = true;
    },
    setErrorMessage(state, error) {
      state.error = error.message;
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
    uriV2: state => `${state.origin}/api/v2`,
    baseUri: state => state.origin,
    ready: state => state.available
  }
});
