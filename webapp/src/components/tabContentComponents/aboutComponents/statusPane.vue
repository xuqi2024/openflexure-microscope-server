<template>
  <div class="host-input">
    <div v-if="$store.state.available">
      <div>
        <div class="uk-margin-small-bottom">
          <b>Microscope Hostname:</b>
          <br />
          {{ $store.state.microscopeHostname }}
        </div>
        <div class="uk-margin-small-bottom">
          <b>API Origin:</b>
          <br />
          {{ $store.state.origin }}
        </div>
        <action-button
          thing="stage"
          action="flash_led"
          submit-label="Flash Illumination"
          :can-terminate="false"
          :submit-data="{ dt: 0.25 }"
        />
      </div>

      <hr />

      <div>
        <b>Server Version:</b> <br />
        TODO
      </div>

      <hr />

      <div class="uk-margin-small-bottom">
        <b>Camera:</b>
        <br />
        <div v-if="'camera' in things">
          {{ things.camera.title }}
        </div>
        <div v-else class="uk-text-danger"><b>No camera configured</b></div>
      </div>
      <div>
        <b>Stage:</b>
        <br />
        <div v-if="'stage' in things">
          {{ things.stage.title }}
        </div>
        <div v-else class="uk-text-danger"><b>No stage configured</b></div>
      </div>

      <hr />

      <div class="uk-grid-small uk-child-width-1-2" uk-grid>
        <div>
          <button
            v-show="'shutdown' in things.system_control.actions"
            class="uk-button uk-button-danger uk-float-right uk-margin uk-margin-remove-top uk-width-1-1"
            @click="systemRequest('shutdown')"
          >
            Shutdown
          </button>
        </div>

        <div>
          <button
            v-show="'reboot' in things.system_control.actions"
            class="uk-button uk-button-danger uk-float-right uk-margin uk-margin-remove-top uk-width-1-1"
            @click="systemRequest('reboot')"
          >
            Restart
          </button>
        </div>
      </div>
    </div>
    <div v-else-if="$store.state.waiting">
      Loading...
    </div>
    <div v-else-if="$store.state.error">
      <b>Error:</b> {{ $store.state.error }}
    </div>
    <div v-else>No active connection</div>
  </div>
</template>

<script>
import axios from "axios";
import ActionButton from "../../labThingsComponents/actionButton.vue";

export default {
  name: "StatusPane",
  components: { ActionButton },

  computed: {
    things: function() {
      return this.$store.getters["wot/thingDescriptions"];
    }
  },

  methods: {
    systemRequest: function(action) {
      this.modalConfirm("Restart microscope?").then(
        () => {
          this.$store.commit("resetState");
          this.$store.commit("wot/deleteAllThingDescriptions");
          // Post and silence errors
          axios
            .post(this.thingActionUrl("system_control", action))
            .catch(() => {});
        },
        () => {}
      );
    }
  }
};
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped lang="less"></style>
