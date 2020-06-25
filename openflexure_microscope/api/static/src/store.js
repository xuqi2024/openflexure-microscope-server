import Vue from "vue";
import Vuex from "vuex";

Vue.use(Vuex);

export default new Vuex.Store({
  state: {
    origin: window.location.origin,
    available: false,
    waiting: false,
    error: "",
    globalSettings: {
      disableStream: false,
      autoGpuPreview: false,
      trackWindow: true,
      appTheme: "system"
    },
    activeStreams: {}
  },

  mutations: {
    changeOrigin(state, origin) {
      state.origin = origin;
    },
    changeWaiting(state, waiting) {
      state.waiting = waiting;
    },
    changeSetting(state, [key, value]) {
      state.globalSettings[key] = value;
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
    uriV2: state => `${state.origin}/api/v2`,
    baseUri: state => state.origin,
    ready: state => state.available
  }
});
