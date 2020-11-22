import Vue from "vue";
import Vuex from "vuex";

Vue.use(Vuex);

interface ActiveStreamMap {
  [key: string]: boolean;
}

class State {
  origin: String = window.location.origin;
  available: Boolean = false;
  waiting: Boolean = false;
  error: String = "";
  disableStream: Boolean = false;
  autoGpuPreview: Boolean = false;
  trackWindow: Boolean = true;
  IHIEnabled: Boolean = false;
  appTheme: String = "system";
  activeStreams: ActiveStreamMap = {};
}

export default new Vuex.Store({
  state: new State(),

  mutations: {
    changeOrigin(state, origin) {
      state.origin = origin;
    },
    changeWaiting(state, waiting) {
      state.waiting = waiting;
    },
    changeDisableStream(state, disabled: boolean) {
      state.disableStream = disabled;
    },
    changeAutoGpuPreview(state, enabled: boolean) {
      state.autoGpuPreview = enabled;
    },
    changeTrackWindow(state, enabled: boolean) {
      state.trackWindow = enabled;
    },
    changeAppTheme(state, theme: string) {
      state.appTheme = theme;
    },
    changeIHIEnabled(state, enabled: boolean) {
      state.IHIEnabled = enabled;
    },
    resetState(state) {
      state.waiting = false;
      state.available = false;
      state.error = "";
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
  },

  actions: {},

  getters: {
    uriV2: (state) => `${state.origin}/api/v2`,
    baseUri: (state) => state.origin,
    ready: (state) => state.available,
  },
});
