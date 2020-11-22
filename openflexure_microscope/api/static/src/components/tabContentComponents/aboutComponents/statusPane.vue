<template>
  <div class="host-input">
    <div v-if="configuration">
      <div>
        <div class="uk-margin-small-bottom">
          <b>API origin:</b>
          <br />
          {{ $store.state.origin }}
          <br />
          <b>API URL:</b>
          <br />
          {{ $store.getters.uriV2 }}
        </div>
      </div>

      <hr />

      <div v-if="settings">
        <b>Device name:</b> <br />
        {{ settings.name }}
      </div>
      <div>
        <b>Server version:</b> <br />
        {{ configuration.application.version }}
      </div>

      <hr />

      <div class="uk-margin-small-bottom">
        <b>Camera:</b>
        <br />
        <div v-if="configuration.camera.type != 'MissingCamera'">
          {{ configuration.camera.type }}
        </div>
        <div v-else class="uk-text-danger">
          <b>No camera connected</b>
        </div>
      </div>
      <div>
        <b>Stage:</b>
        <br />
        <div v-if="configuration.stage.type != 'MissingStage'">
          {{ configuration.stage.type }}
        </div>
        <div v-else class="uk-text-danger">
          <b>No stage connected</b>
        </div>
      </div>

      <hr />

      <div class="uk-grid-small uk-child-width-1-2" uk-grid>
        <div>
          <button
            v-show="'shutdown' in systemActionLinks"
            class="uk-button uk-button-danger uk-float-right uk-margin uk-margin-remove-top uk-width-1-1"
            @click="shutdownRequest"
          >
            Shutdown
          </button>
        </div>

        <div>
          <button
            v-show="'reboot' in systemActionLinks"
            class="uk-button uk-button-danger uk-float-right uk-margin uk-margin-remove-top uk-width-1-1"
            @click="rebootRequest"
          >
            Restart
          </button>
        </div>
      </div>
    </div>
    <div v-else-if="$store.state.waiting">Loading...</div>
    <div v-else-if="$store.state.error">
      <b>Error:</b> {{ $store.state.error }}
    </div>
    <div v-else>No active connection</div>
  </div>
</template>

<script>
import axios from "axios";

export default {
  name: "StatusPane",

  components: {},

  data: function () {
    return {
      configuration: null,
      settings: null,
      systemActionLinks: {},
    };
  },

  computed: {
    settingsUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/instrument/settings`;
    },
    configurationUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/instrument/configuration`;
    },
    rootUri: function () {
      return `${this.$store.getters.baseUri}/api/v2`;
    },
  },

  mounted: function () {
    // Watch for host 'ready', then update configuration
    this.updateConfiguration();
    this.updateSettings();
    this.updateSystemActions();
  },

  methods: {
    updateConfiguration: function () {
      axios
        .get(this.configurationUri)
        .then((response) => {
          this.configuration = response.data;
        })
        .catch((error) => {
          this.modalError(error); // Let mixin handle error
        });
    },
    updateSettings: function () {
      axios
        .get(this.settingsUri)
        .then((response) => {
          this.settings = response.data;
        })
        .catch((error) => {
          this.modalError(error); // Let mixin handle error
        });
    },
    updateSystemActions: function () {
      axios
        .get(this.rootUri)
        .then((response) => {
          if ("RebootAPI" in response.data.actions) {
            this.$set(
              this.systemActionLinks,
              "reboot",
              `${this.$store.getters.baseUri}/api/v2/actions/system/reboot/`
            );
          } else {
            delete this.systemActionLinks.reboot;
          }
          if ("ShutdownAPI" in response.data.actions) {
            this.$set(
              this.systemActionLinks,
              "shutdown",
              `${this.$store.getters.baseUri}/api/v2/actions/system/shutdown/`
            );
          } else {
            delete this.systemActionLinks.shutdown;
          }
        })
        .catch((error) => {
          this.modalError(error); // Let mixin handle error
        });
    },
    shutdownRequest: function () {
      this.modalConfirm("Shut down microscope?").then(() => {
        if ("shutdown" in this.systemActionLinks) {
          this.$store.commit("resetState");
          axios.post(this.systemActionLinks.shutdown).catch((error) => {
            console.log(error); // Be quiet when empty response is recieved
          });
        }
      });
    },
    rebootRequest: function () {
      this.modalConfirm("Restart microscope?").then(() => {
        if ("reboot" in this.systemActionLinks) {
          this.$store.commit("resetState");
          axios.post(this.systemActionLinks.reboot).catch((error) => {
            console.log(error); // Be quiet when empty response is recieved
          });
        }
      });
    },
  },
};
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped lang="less"></style>
