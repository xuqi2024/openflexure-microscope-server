import Vue from "vue";
import Vuex from "vuex";

Vue.use(Vuex);

interface ActiveStream {
  [streamID: string]: boolean;
}

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
      IHIEnabled: false,
      appTheme: "system"
    },
    activeStreams: <ActiveStream> {}
  },

  mutations: {
    changeOrigin(state, origin) {
      state.origin = origin;
    },
    changeWaiting(state, waiting) {
      state.waiting = waiting;
    },
    changeDisableStream(state, disabled: boolean) {
      state.globalSettings.disableStream = disabled;
    },
    changeAutoGpuPreview(state, enabled: boolean) {
      state.globalSettings.autoGpuPreview = enabled;
    },
    changeTrackWindow(state, enabled: boolean) {
      state.globalSettings.trackWindow = enabled;
    },
    changeAppTheme(state, theme: string) {
      state.globalSettings.appTheme = theme;
    },
    changeIHIEnabled(state, enabled: boolean) {
      state.globalSettings.IHIEnabled = enabled;
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
    }
  },

  actions: {},

  getters: {
    uriV2: state => `${state.origin}/api/v2`,
    baseUri: state => state.origin,
    ready: state => state.available
  }
});
